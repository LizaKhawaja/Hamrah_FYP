#passanger request seat, driver accept/reject ride, passanger can cancel request, passanger search rides

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from .. import models, schemas, database, oauth2
from ..utils import haversine, within_time_window, is_along_the_way
from typing import Optional
from ..dependencies import require_driver, require_passenger
from ..services.location_service import location_manager
import asyncio
from ..services.notification_logic import (
    notify_driver_new_request,
    notify_passenger_request_accepted,
    notify_passenger_request_rejected,
    notify_driver_request_cancelled,
)
from ..services.driver_feed_service import driver_feed_manager

router = APIRouter(prefix="/ride_requests", tags=["Ride Requests"])

PKT = timezone(timedelta(hours=5))


def normalize_departure_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(PKT).replace(tzinfo=None)


#request a ride
@router.post("/", response_model=schemas.RideRequestOut, status_code=status.HTTP_201_CREATED)
async def request_ride(
    data: schemas.RideRequestCreate,
    db: Session = Depends(database.get_db),
    current_user=Depends(oauth2.get_current_user)
):
    ride = db.query(models.Ride).filter(models.Ride.id == data.ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride.driver_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot request your own ride")

    now = datetime.now(PKT).replace(tzinfo=None)
    dep = normalize_departure_time(ride.departure_time)

    if ride.status != "active":
        raise HTTPException(status_code=400, detail="Ride is not available")

    if dep <= now:
        raise HTTPException(status_code=400, detail="Ride departure time has passed")

    if ride.seats_available <= 0:
        ride.status = "full"
        db.commit()
        raise HTTPException(status_code=400, detail="Ride is full")

    existing = db.query(models.RideRequest).filter(
        models.RideRequest.ride_id == ride.id,
        models.RideRequest.passenger_id == current_user.id,
        models.RideRequest.status.in_(["pending", "accepted"])
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You already have an active request for this ride")

    ride_request = models.RideRequest(
        ride_id=ride.id,
        passenger_id=current_user.id,
        status="pending",
        distance_from_route=0.0,
        pickup_lat=data.pickup_lat,
        pickup_lng=data.pickup_lng
    )

    db.add(ride_request)
    db.commit()
    db.refresh(ride_request)

    passenger_name = f"{current_user.first_name} {current_user.last_name}"
    await driver_feed_manager.send_to_driver(ride.driver_id, {
        "type": "new_ride_request",
        "request": {
            "id": ride_request.id,
            "ride_id": ride_request.ride_id,
            "status": ride_request.status,
            "passenger_id": current_user.id,
            "passenger_name": passenger_name,
            "passenger_email": current_user.email,
            "pickup_lat": ride_request.pickup_lat,
            "pickup_lng": ride_request.pickup_lng,
            "from_address": ride.from_address,
            "to_address": ride.to_address,
            "departure_time": ride.departure_time.isoformat() if ride.departure_time else None,
            "fare": ride.fare_per_seat,
            "distance_from_route": ride_request.distance_from_route,
        },
    })

    try:
        notify_driver_new_request(db, driver_id=ride.driver_id, passenger_id=current_user.id)
    except Exception as e:
        print(f"Notification failed: {e}")

    return ride_request

@router.websocket("/ws/driver")
async def driver_ride_requests_ws(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        token_data = oauth2.verify_access_token(
            token,
            HTTPException(status_code=403, detail="Invalid token")
        )
    except Exception:
        await websocket.close(code=1008)
        return

    db = database.SessionLocal()
    try:
        driver = db.query(models.User).filter(models.User.id == token_data.id).first()
        if not driver or not driver.is_driver:
            await websocket.close(code=1008)
            return
    finally:
        db.close()

    await driver_feed_manager.connect(token_data.id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        driver_feed_manager.disconnect(token_data.id, websocket)

#driver accepts request
@router.post("/{request_id}/accept", response_model=schemas.RideRequestOut)
def accept_request(
    request_id: int,
    db: Session = Depends(database.get_db),
    current_user=Depends(require_driver)
):
    req = db.query(models.RideRequest).filter(models.RideRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    ride = db.query(models.Ride).filter(models.Ride.id == req.ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride.driver_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only manage requests for your own ride")

    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot accept request with status '{req.status}'")

    if ride.status != "active":
        raise HTTPException(status_code=400, detail="Ride is not available")

    if ride.seats_available <= 0:
        ride.status = "full"
        db.commit()
        raise HTTPException(status_code=400, detail="Ride is full")

    req.status = "accepted"
    ride.seats_available -= 1

    if ride.seats_available == 0:
        ride.status = "full"

    db.commit()
    db.refresh(req)

    try:
        notify_passenger_request_accepted(db, passenger_id=req.passenger_id, driver_id=current_user.id)
    except Exception as e:
        print(f"Notification failed: {e}")

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(location_manager.broadcast_location(req.ride_id, {
            "type": "passenger_status_update",
            "request_id": req.id,
            "passenger_id": req.passenger_id,
            "status": "accepted",
            "request_status": "accepted",
        }))
    except RuntimeError:
        pass

    return req


@router.post("/{request_id}/reject", response_model=schemas.RideRequestOut)
def reject_request(
    request_id: int,
    db: Session = Depends(database.get_db),
    current_user=Depends(require_driver)
):
    req = db.query(models.RideRequest).filter(models.RideRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    ride = db.query(models.Ride).filter(models.Ride.id == req.ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride.driver_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only manage requests for your own ride")

    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot reject request with status '{req.status}'")

    req.status = "rejected"
    db.commit()
    db.refresh(req)

    try:
        notify_passenger_request_rejected(db, passenger_id=req.passenger_id, driver_id=current_user.id)
    except Exception as e:
        print(f"Notification failed: {e}")

    return req


@router.post("/{request_id}/cancel", response_model=schemas.RideRequestOut)
def cancel_request(
    request_id: int,
    db: Session = Depends(database.get_db),
    current_user=Depends(require_passenger)
):
    req = db.query(models.RideRequest).filter(models.RideRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if req.passenger_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only cancel your own request")

    if req.status not in ["pending", "pickup", "riding", "accepted"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel request with status '{req.status}'")

    ride = db.query(models.Ride).filter(models.Ride.id == req.ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    was_accepted = req.status in ("pickup", "riding", "accepted")
    req.status = "cancelled_by_passenger"

    if was_accepted:
        ride.seats_available += 1
        if ride.status == "full":
            ride.status = "active"

    db.commit()
    db.refresh(req)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(location_manager.broadcast_location(ride.id, {
            "type": "status_update",
            "status": "cancelled"
        }))
    except RuntimeError:
        try:
            asyncio.run(location_manager.broadcast_location(ride.id, {
                "type": "status_update",
                "status": "cancelled"
            }))
        except Exception as ws_err:
            print(f"WS cancel broadcast failed: {ws_err}")
    except Exception as ws_err:
        print(f"WS cancel broadcast failed: {ws_err}")

    try:
        notify_driver_request_cancelled(db, driver_id=ride.driver_id, passenger_id=current_user.id)
    except Exception as e:
        print(f"Notification failed: {e}")

    return req


@router.get("/active")
def get_active_ride(
    db: Session = Depends(database.get_db),
    current_user=Depends(oauth2.get_current_user)
):
    print(f"[DEBUG /active] current_user.id={current_user.id}, dsu_reg_id={current_user.dsu_reg_id}")
    req = db.query(models.RideRequest).filter(
        models.RideRequest.passenger_id == current_user.id,
        models.RideRequest.status.in_(['pending', 'accepted', 'pickup', 'riding'])
    ).order_by(models.RideRequest.id.desc()).first()

    if not req:
        return None

    ride = db.query(models.Ride).filter(models.Ride.id == req.ride_id).first()
    driver = db.query(models.User).filter(models.User.id == ride.driver_id).first() if ride else None
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.user_id == ride.driver_id).first() if ride else None

    driver_location = db.query(models.RideLocation).filter(
        models.RideLocation.ride_id == req.ride_id
    ).order_by(models.RideLocation.timestamp.desc()).first()

    eta_minutes = None
    if driver_location and ride and ride.from_lat and ride.from_lng:
        from math import radians, sin, cos, sqrt, atan2
        R = 6371
        lat1 = radians(driver_location.latitude)
        lon1 = radians(driver_location.longitude)
        lat2 = radians(ride.from_lat)
        lon2 = radians(ride.from_lng)
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
        dist_km = R * 2 * atan2(sqrt(a), sqrt(1-a))
        eta_minutes = max(1, round((dist_km / 30) * 60))

    ride_status = req.status
    status_map = {
        'pending':   'Waiting for driver to accept',
        'accepted':  'Driver accepted, on the way',
        'active':    'Driver accepted, on the way',
        'pickup':    '📍 Driver has arrived!',
        'arrived':   '📍 Driver has arrived!',
        'ongoing':   '🚗 Ride in progress',
        'riding':    '🚗 Ride in progress',
        'dropped':   '✅ Ride completed',
        'completed': '✅ Ride completed',
    }

    return {
        'request_id':   req.id,
        'status':       ride_status,
        'status_label': status_map.get(ride_status, ride_status),
        'request_status': req.status,
        'ride_id':      ride.id if ride else None,
        'from_address': ride.from_address if ride else '',
        'to_address':   ride.to_address if ride else '',
        'departure_time': ride.departure_time.isoformat() if ride else None,
        'fare_per_seat': ride.fare_per_seat if ride else 0,
        'driver_name':  f"{driver.first_name} {driver.last_name}" if driver else 'Driver',
        'vehicle_number': vehicle.vehicle_number if vehicle else '',
        'driver_id':    ride.driver_id if ride else None,
        'eta_minutes':  eta_minutes,
    }


@router.get("/history")
def passenger_ride_history(
    db: Session = Depends(database.get_db),
    current_user=Depends(oauth2.get_current_user)
):
    requests = db.query(models.RideRequest).filter(
        models.RideRequest.passenger_id == current_user.id
    ).order_by(models.RideRequest.id.desc()).all()

    result = []
    for req in requests:
        ride = db.query(models.Ride).filter(models.Ride.id == req.ride_id).first()
        if not ride:
            continue
        driver = db.query(models.User).filter(models.User.id == ride.driver_id).first()
        vehicle = db.query(models.Vehicle).filter(models.Vehicle.user_id == ride.driver_id).first()
        # Map new statuses to human-readable labels for history
        status_label_map = {
            'pickup': 'Accepted',
            'riding': 'In Progress',
            'dropped': 'Completed',
            'rated': 'Completed',
            'completed': 'Completed',
            'accepted': 'Accepted',
            'picked_up': 'In Progress',
            'cancelled_by_passenger': 'Cancelled',
            'cancelled_by_driver': 'Cancelled',
            'pending': 'Pending',
            'rejected': 'Rejected',
        }
        result.append({
            'id': req.id,
            'status': status_label_map.get(req.status, req.status),
            'raw_status': req.status,
            'fare': ride.fare_per_seat,
            'from_address': ride.from_address,
            'to_address': ride.to_address,
            'departure_time': ride.departure_time.isoformat() if ride.departure_time else None,
            'driver_name': f"{driver.first_name} {driver.last_name}" if driver else 'Unknown',
            'vehicle_number': vehicle.vehicle_number if vehicle else '',
            'vehicle_model': vehicle.vehicle_model if vehicle else '',
        })
    return result

#for ride search
@router.get("/search", response_model=list[schemas.RideOut])
def search_rides(
    from_lat: float,
    from_lng: float,
    to_lat: float,
    to_lng: float,
    target_time: datetime,
    mode_of_transport: Optional[str] = None,
    ac: Optional[bool] = None,
    gender: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user=Depends(oauth2.get_current_user)
):
    now = datetime.now(PKT).replace(tzinfo=None)
    target_time = normalize_departure_time(target_time)
    rides = db.query(models.Ride).filter(
        models.Ride.departure_time > now,
        models.Ride.status == "active",
        models.Ride.seats_available > 0
    ).all()

    print(f"[SEARCH] Total active rides: {len(rides)}, target_time={target_time}")
    results = []
    for ride in rides:
        route_points = [(ride.from_lat, ride.from_lng)]
        extra_points = db.query(models.RidePickupPoint).filter(
            models.RidePickupPoint.ride_id == ride.id
        ).order_by(models.RidePickupPoint.order_index).all()
        for pp in extra_points:
            route_points.append((pp.lat, pp.lng))
        route_points.append((ride.to_lat, ride.to_lng))

        along_way = is_along_the_way(from_lat, from_lng, to_lat, to_lng, route_points, threshold_km=7.0)
        print(f"  Ride {ride.id}: along_way={along_way}, dep={ride.departure_time}, gender={ride.gender_filter}")

        if not along_way:
            print(f"  -> SKIP: not along the driver's path")
            continue

        if not within_time_window(ride.departure_time, target_time, margin_minutes=20):
            print(f"  -> SKIP: time window mismatch")
            continue

        if mode_of_transport is not None:
            try:
                if ride.vehicle.mode_of_transport != mode_of_transport:
                    print(f"  -> SKIP: transport mismatch")
                    continue
            except Exception:
                pass

        if gender is not None and ride.gender_filter not in ("any", gender):
            print(f"  -> SKIP: gender mismatch")
            continue

        print(f"  -> MATCH")
        results.append(ride)

    print(f"[SEARCH] Results: {len(results)}")

    # Add driver info to each ride
    output = []
    for ride in results:
        driver = db.query(models.User).filter(models.User.id == ride.driver_id).first()
        vehicle = db.query(models.Vehicle).filter(models.Vehicle.user_id == ride.driver_id).first()
        # Get driver rating
        avg_rating = db.query(func.avg(models.Rating.stars)).filter(
            models.Rating.driver_id == ride.driver_id).scalar() or 0.0

        # Count completed rides for driver
        driver_completed_rides = db.query(models.Ride).filter(
            models.Ride.driver_id == ride.driver_id,
            models.Ride.status == 'completed'
        ).count()


        ride_dict = {
            'id': ride.id,
            'driver_id': ride.driver_id,
            'vehicle_id': ride.vehicle_id,
            'from_address': ride.from_address,
            'to_address': ride.to_address,
            'departure_time': ride.departure_time,
            'seats_available': ride.seats_available or 1,
            'ac': ride.ac,
            'gender_filter': ride.gender_filter,
            'fare_per_seat': ride.fare_per_seat,
            'mode_of_transport': vehicle.mode_of_transport if vehicle else None,
            'status': ride.status,
            'driver_name': f"{driver.first_name} {driver.last_name}" if driver else 'Driver',
            'driver_phone': driver.phone_number if driver else '',
            'driver_rating': round(float(avg_rating), 1),
            'vehicle_number': vehicle.vehicle_number if vehicle else '',
            'total_rides': driver_completed_rides,
            'pickup_points': [
                {'address': pp.address, 'lat': pp.lat, 'lng': pp.lng, 'order_index': pp.order_index}
                for pp in db.query(models.RidePickupPoint).filter(
                    models.RidePickupPoint.ride_id == ride.id
                ).order_by(models.RidePickupPoint.order_index).all()
            ],
        }
        output.append(ride_dict)

    return output
