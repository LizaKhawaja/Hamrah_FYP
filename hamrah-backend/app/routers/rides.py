#Driver ride offer, driver can view all his rides, driver complete ride and driver can cancel ride
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from ..database import get_db
from ..models import Ride, User, Vehicle, RideRequest, RidePickupPoint
from ..schemas import RideOut, RideCreate
from ..dependencies import require_driver
import asyncio
from ..services.location_service import location_manager
from ..services.notification_logic import (
    notify_passengers_ride_completed,
    notify_passengers_ride_cancelled,
)

router = APIRouter(prefix="/rides", tags=["Rides"])

PKT = timezone(timedelta(hours=5))


def normalize_departure_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(PKT).replace(tzinfo=None)


@router.post("/", response_model=RideOut, status_code=status.HTTP_201_CREATED)
def post_ride(
    ride: RideCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == ride.vehicle_id,
        Vehicle.user_id == current_user.id
    ).first()
    if not vehicle:
        raise HTTPException(status_code=400, detail="Invalid vehicle selection")

    now = datetime.now(PKT).replace(tzinfo=None)
    dep = normalize_departure_time(ride.departure_time)
    if dep <= now:
        raise HTTPException(status_code=400, detail="departure_time must be in the future")


    if vehicle.mode_of_transport == "bike":
        if ride.seats_available is not None:
            raise HTTPException(status_code=400, detail="seats_available is not allowed for bike rides")
        if ride.ac is not None:
            raise HTTPException(status_code=400, detail="ac is not allowed for bike rides")
        seats = 1
        ac_value = None

    elif vehicle.mode_of_transport == "car":
        if ride.seats_available is None or ride.seats_available < 1:
            raise HTTPException(status_code=400, detail="seats_available is required for car rides and must be >= 1")
        if ride.ac is None:
            raise HTTPException(status_code=400, detail="ac is required for car rides (true/false)")
        seats = ride.seats_available
        ac_value = ride.ac

    else:
        raise HTTPException(status_code=400, detail="Invalid mode_of_transport on vehicle")

    new_ride = Ride(
        driver_id=current_user.id,
        vehicle_id=vehicle.id,
        from_address=ride.from_address,
        from_lat=ride.from_lat,
        from_lng=ride.from_lng,
        to_address=ride.to_address,
        to_lat=ride.to_lat,
        to_lng=ride.to_lng,
        departure_time=dep,
        seats_available=seats,
        ac=ac_value,
        fare_per_seat=ride.fare_per_seat,
        gender_filter=ride.gender_filter,
        status="active",
    )

    db.add(new_ride)
    db.flush() 
    
    if ride.pickup_points:
        for pp in ride.pickup_points:
            db.add(RidePickupPoint(
                ride_id=new_ride.id,
                address=pp.address,
                lat=pp.lat,
                lng=pp.lng,
                order_index=pp.order_index,
            ))

    db.commit()
    db.refresh(new_ride)
    return new_ride


@router.get("/active")
def driver_active_rides(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    rides = db.query(Ride).filter(
        Ride.driver_id == current_user.id,
        Ride.status.in_(["active", "full", "ongoing", "completed"]),
    ).order_by(Ride.departure_time.asc()).all()

    result = []
    for ride in rides:
        accepted = db.query(RideRequest).filter(
            RideRequest.ride_id == ride.id,
            RideRequest.passenger_id.isnot(None),
            RideRequest.status.in_(["accepted", "pickup", "riding", "dropped", "rated",
                                     "picked_up", "arrived", "completed"]),
        ).all()
        passengers = []
        for req in accepted:
            p = db.query(User).filter(User.id == req.passenger_id).first()
            if p:
                passengers.append({
                    "id": p.id,
                    "name": f"{p.first_name} {p.last_name}",
                    "phone": p.phone_number or "",
                    "request_id": req.id,
                    "status": req.status,
                    "fare": ride.fare_per_seat,
                })
        active_passengers = [p for p in passengers if p["status"] not in ("dropped", "rated")]
        result.append({
            "id": ride.id,
            "driver_id": ride.driver_id,
            "vehicle_id": ride.vehicle_id,
            "from_address": ride.from_address,
            "to_address": ride.to_address,
            "departure_time": ride.departure_time.isoformat() if ride.departure_time else None,
            "seats_available": ride.seats_available or 1,
            "ac": ride.ac,
            "gender_filter": ride.gender_filter,
            "fare_per_seat": ride.fare_per_seat,
            "status": ride.status,
            "passenger": passengers[0] if passengers else None,
            "accepted_passengers": passengers,
            "accepted_count": len(active_passengers),
        })
    return result


@router.get("/my")
def my_rides(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    rides = db.query(Ride).filter(Ride.driver_id == current_user.id).all()
    result = []
    for ride in rides:
        from ..models import RideRequest
        accepted = db.query(RideRequest).filter(
            RideRequest.ride_id == ride.id,
            RideRequest.passenger_id.isnot(None),
            RideRequest.status.in_(["pickup", "riding", "dropped", "rated",
                                     "accepted", "picked_up", "arrived", "completed"]),
        ).all()
        passengers = []
        for req in accepted:
            p = db.query(User).filter(User.id == req.passenger_id).first()
            if p:
                passengers.append({
                    'id': p.id,
                    'name': f"{p.first_name} {p.last_name}",
                    'phone': p.phone_number or '',
                    'request_id': req.id,
                    'status': req.status,
                    'fare': ride.fare_per_seat,
                })
        result.append({
            'id': ride.id,
            'driver_id': ride.driver_id,
            'vehicle_id': ride.vehicle_id,
            'from_address': ride.from_address,
            'to_address': ride.to_address,
            'departure_time': ride.departure_time.isoformat() if ride.departure_time else None,
            'seats_available': ride.seats_available or 1,
            'ac': ride.ac,
            'gender_filter': ride.gender_filter,
            'fare_per_seat': ride.fare_per_seat,
            'status': ride.status,
            'passenger': passengers[0] if passengers else None,
            'accepted_passengers': passengers,
            'accepted_count': len(passengers),
        })
    return result


@router.get("/requests")
def driver_ride_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    from ..models import RideRequest, DSUStudent
    my_ride_ids = [r.id for r in db.query(Ride).filter(
        Ride.driver_id == current_user.id).all()]
    if not my_ride_ids:
        return []
    requests = db.query(RideRequest).filter(
        RideRequest.ride_id.in_(my_ride_ids),
        RideRequest.status == 'pending'
    ).all()
    result = []
    for req in requests:
        ride = db.query(Ride).filter(Ride.id == req.ride_id).first()
        passenger = db.query(User).filter(User.id == req.passenger_id).first()
        result.append({
            'id': req.id,
            'ride_id': req.ride_id,
            'status': req.status,
            'passenger_name': f"{passenger.first_name} {passenger.last_name}" if passenger else 'Unknown',
            'passenger_email': passenger.email if passenger else '',
            'from_address': ride.from_address if ride else '',
            'to_address': ride.to_address if ride else '',
            'fare': ride.fare_per_seat if ride else 0,
            'distance_from_route': getattr(req, 'distance_from_route', 0.0),
        })
    return result

@router.post("/requests/{request_id}/pickup")
def pickup_passenger(
    request_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_driver)
):
    req = db.query(RideRequest).filter(RideRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status not in ("pickup", "arrived"):
        raise HTTPException(status_code=400, detail="Cannot start ride only after driver has arrived at pickup")
    req.status = "riding"

    ride = db.query(Ride).filter(Ride.id == req.ride_id).first()
    if ride and ride.status in ("active", "full"):
        ride.status = "ongoing"

    db.commit()
    try:
        from ..services.notification_logic import notify_passenger_picked_up
        notify_passenger_picked_up(db, passenger_id=req.passenger_id, driver_id=current_user.id)
    except Exception as e:
        print(f"Notification failed: {e}")

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(location_manager.broadcast_location(req.ride_id, {
            "type": "passenger_status_update",
            "request_id": req.id,
            "passenger_id": req.passenger_id,
            "status": "riding",
        }))
    except RuntimeError:
        pass
    return {"message": "Passenger marked as riding"}


@router.post("/requests/{request_id}/arrive")
def arrive_passenger(
    request_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_driver)
):
    req = db.query(RideRequest).filter(RideRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status == "pickup":
        return {"message": "Driver already marked as arrived"}
    req.status = "pickup"
    db.commit()
    try:
        from ..services.notification_logic import notify_passenger_arrived
        notify_passenger_arrived(db, passenger_id=req.passenger_id, driver_id=current_user.id)
    except Exception as e:
        print(f"Notification failed: {e}")
    
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(location_manager.broadcast_location(req.ride_id, {
            "type": "passenger_status_update",
            "request_id": req.id,
            "passenger_id": req.passenger_id,
            "status": "arrived",
            "request_status": "pickup",
        }))
    except RuntimeError:
        pass
    return {"message": "Driver marked as arrived — passenger notified"}


@router.post("/requests/{request_id}/complete")
def complete_passenger_ride(
    request_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_driver)
):
    req = db.query(RideRequest).filter(RideRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    req.status = "dropped"
    db.commit()

    try:
        from ..services.notification_logic import notify_passengers_ride_completed
        notify_passengers_ride_completed(db, passenger_ids=[req.passenger_id], driver_id=current_user.id)
    except Exception as e:
        print(f"Notification failed: {e}")

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(location_manager.broadcast_location(req.ride_id, {
            "type": "passenger_status_update",
            "request_id": req.id,
            "passenger_id": req.passenger_id,
            "status": "dropped",
        }))
    except RuntimeError:
        pass

    ride = db.query(Ride).filter(Ride.id == req.ride_id).first()
    if ride:
        still_active_count = db.query(RideRequest).filter(
            RideRequest.ride_id == ride.id,
            RideRequest.status.in_(["pickup", "riding"])
        ).count()
        if still_active_count == 0:
            ride.status = "completed"
            db.commit()
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(location_manager.broadcast_location(ride.id, {
                    "type": "status_update",
                    "status": "completed",
                }))
            except RuntimeError:
                pass

    return {"message": "Passenger marked as dropped"}


@router.post("/{ride_id}/complete")
def complete_ride(
    ride_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_driver)
):
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride.driver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the driver can complete this ride")

    if ride.status not in ("ongoing", "arrived", "active", "full"):
        raise HTTPException(status_code=400, detail=f"Ride cannot be completed — current status is {ride.status}")

    not_picked = db.query(RideRequest).filter(
        RideRequest.ride_id == ride_id,
        RideRequest.status == "accepted"
    ).count()

    ride.status = "completed"

    db.query(RideRequest).filter(
        RideRequest.ride_id == ride_id,
        RideRequest.status.in_(["pickup", "riding", "accepted", "picked_up", "arrived"])
    ).update({"status": "dropped"}, synchronize_session=False)

    db.commit()

    completed_requests = db.query(RideRequest).filter(
        RideRequest.ride_id == ride_id,
        RideRequest.status.in_(["dropped", "completed"])
    ).all()
    passenger_ids = [r.passenger_id for r in completed_requests]

    try:
        notify_passengers_ride_completed(db, passenger_ids=passenger_ids, driver_id=current_user.id)
    except Exception as e:
        print(f"Notification failed: {e}")

    from ..services.location_service import location_manager
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(location_manager.broadcast_location(ride_id, {
            "type": "status_update",
            "status": "completed",
        }))
    except RuntimeError:
        pass

    return {"message": "Ride completed successfully", "ride_id": ride_id}


@router.patch("/{ride_id}")
def edit_ride(
    ride_id: int,
    ride_update: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_driver)
):

    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    if ride.driver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your ride")
    if ride.status != "active":
        raise HTTPException(status_code=400, detail="Can only edit active rides")

    if "fare_per_seat" in ride_update:
        ride.fare_per_seat = ride_update["fare_per_seat"]
    if "seats_available" in ride_update:
        ride.seats_available = ride_update["seats_available"]
    if "gender_filter" in ride_update:
        ride.gender_filter = ride_update["gender_filter"]
    if "departure_time" in ride_update:
        ride.departure_time = normalize_departure_time(
            datetime.fromisoformat(ride_update["departure_time"])
        )

    db.commit()
    return {"message": "Ride updated", "ride_id": ride_id}


@router.delete("/{ride_id}")
def delete_ride(
    ride_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_driver)
):
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    if ride.driver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your ride")
    if ride.status != "active":
        raise HTTPException(status_code=400, detail="Can only delete active rides with no passengers")

    # Check no accepted passengers
    accepted = db.query(RideRequest).filter(
        RideRequest.ride_id == ride_id,
        RideRequest.passenger_id.isnot(None),
        RideRequest.status.in_(["accepted", "confirmed", "picked_up"]),
    ).count()
    if accepted > 0:
        raise HTTPException(status_code=400, detail="Cannot delete ride with accepted passengers")

    # Delete related requests first
    db.query(RideRequest).filter(RideRequest.ride_id == ride_id).delete()
    db.delete(ride)
    db.commit()
    return {"message": "Ride deleted", "ride_id": ride_id}


@router.post("/{ride_id}/cancel")
def cancel_ride(
    ride_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_driver)
):
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride.driver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the driver can cancel this ride")

    if ride.status in ["completed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Ride already {ride.status}")

    affected = db.query(RideRequest).filter(
        RideRequest.ride_id == ride_id,
        RideRequest.status.in_(["pending", "accepted"])
    ).all()
    passenger_ids = [r.passenger_id for r in affected]

    ride.status = "cancelled"
    for r in affected:
        r.status = "cancelled_by_driver"
    db.commit()

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(location_manager.broadcast_location(ride_id, {
            "type": "status_update",
            "status": "cancelled"
        }))
    except RuntimeError:
        try:
            asyncio.run(location_manager.broadcast_location(ride_id, {
                "type": "status_update",
                "status": "cancelled"
            }))
        except Exception as ws_err:
            print(f"WS cancel broadcast failed: {ws_err}")
    except Exception as ws_err:
        print(f"WS cancel broadcast failed: {ws_err}")

    try:
        notify_passengers_ride_cancelled(db, passenger_ids=passenger_ids, driver_id=current_user.id)
    except Exception as e:
        print(f"Notification failed: {e}")

    return {"message": "Ride cancelled", "ride_id": ride_id}
