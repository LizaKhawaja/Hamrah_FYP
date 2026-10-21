from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import models, schemas, database, oauth2
from ..dependencies import require_passenger

router = APIRouter(prefix="/ratings", tags=["Ratings"])


@router.post("/", response_model=schemas.RatingOut, status_code=status.HTTP_201_CREATED)
def submit_rating(
    data: schemas.RatingCreate,
    db: Session = Depends(database.get_db),
    current_user=Depends(oauth2.get_current_user),
):
    ride = db.query(models.Ride).filter(models.Ride.id == data.ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride.status != "completed":
        raise HTTPException(status_code=400, detail="You can only rate a completed ride")

    # passenger must have an accepted request on this ride
    ride_request = db.query(models.RideRequest).filter(
        models.RideRequest.ride_id == data.ride_id,
        models.RideRequest.passenger_id == current_user.id,
        models.RideRequest.status.in_(["accepted", "picked_up", "arrived", "riding", "dropped", "completed", "rated", "finished"]),
    ).first()
    if not ride_request:
        import logging
        logger = logging.getLogger(__name__)
        all_requests_for_ride = db.query(models.RideRequest).filter(models.RideRequest.ride_id == data.ride_id).all()
        logger.info(f"Rating submission failed for passenger {current_user.id} on ride {data.ride_id}")
        logger.info(f"All requests for ride {data.ride_id}: {[{'id': r.id, 'passenger_id': r.passenger_id, 'status': r.status} for r in all_requests_for_ride]}")
        raise HTTPException(status_code=403, detail="You were not a passenger on this ride")
    existing = db.query(models.Rating).filter(
        models.Rating.ride_id == data.ride_id,
        models.Rating.passenger_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already rated this ride")

    rating = models.Rating(
        ride_id=data.ride_id,
        passenger_id=current_user.id,
        driver_id=ride.driver_id,
        stars=data.stars,
        tags=data.tags,
        review=data.review,
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


@router.post("/passenger", response_model=schemas.PassengerRatingOut, status_code=status.HTTP_201_CREATED)
def submit_passenger_rating(
    data: schemas.PassengerRatingCreate,
    db: Session = Depends(database.get_db),
    current_user=Depends(oauth2.get_current_user),
):
    if not current_user.is_driver:
        raise HTTPException(status_code=403, detail="Only drivers can rate passengers")

    ride = db.query(models.Ride).filter(models.Ride.id == data.ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride.driver_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the driver of this ride")

    if ride.status != "completed":
        raise HTTPException(status_code=400, detail="You can only rate passengers of a completed ride")

    ride_request = db.query(models.RideRequest).filter(
        models.RideRequest.ride_id == data.ride_id,
        models.RideRequest.passenger_id == data.passenger_id,
        models.RideRequest.status.in_(["accepted", "completed", "picked_up", "arrived"]),
    ).first()
    if not ride_request:
        raise HTTPException(status_code=400, detail="This user is not a passenger on this ride")

    existing = db.query(models.PassengerRating).filter(
        models.PassengerRating.ride_id == data.ride_id,
        models.PassengerRating.passenger_id == data.passenger_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already rated this passenger for this ride")

    rating = models.PassengerRating(
        ride_id=data.ride_id,
        passenger_id=data.passenger_id,
        driver_id=current_user.id,
        stars=data.stars,
        tags=data.tags,
        review=data.review,
    )
    db.add(rating)

    if ride_request:
        ride_request.status = "rated"

    db.commit()
    db.refresh(rating)

    unrated_count = db.query(models.RideRequest).filter(
        models.RideRequest.ride_id == data.ride_id,
        models.RideRequest.status.in_(["dropped", "completed"]),
    ).count()

    return rating


@router.get("/unrated", response_model=list[schemas.UnratedRideOut])
def get_unrated_rides(
    db: Session = Depends(database.get_db),
    current_user=Depends(oauth2.get_current_user),
):
    import logging
    logger = logging.getLogger(__name__)
    all_requests = db.query(models.RideRequest).filter(
        models.RideRequest.passenger_id == current_user.id,
        models.RideRequest.status.in_(["dropped", "completed", "rated", "finished"])
    ).all()
    logger.info(f"Found {len(all_requests)} requests for passenger {current_user.id}: {[{'id': r.id, 'ride_id': r.ride_id, 'status': r.status} for r in all_requests]}")

    unrated = []
    for req in all_requests:
        if not req.ride_id:
            continue

        ride = db.query(models.Ride).filter(models.Ride.id == req.ride_id).first()
        if not ride:
            continue

        request_done = req.status in ["dropped", "completed", "rated", "finished"]
        ride_done = ride.status in ["completed", "finished", "ended"]
        if not (request_done or ride_done):
            continue

        existing = db.query(models.Rating).filter(
            models.Rating.ride_id == req.ride_id,
            models.Rating.passenger_id == current_user.id,
        ).first()
        if existing:
            continue

        driver = db.query(models.User).filter(models.User.id == ride.driver_id).first()

        vehicle_number = ""
        try:
            if ride.vehicle and ride.vehicle.vehicle_number:
                vehicle_number = ride.vehicle.vehicle_number
        except Exception:
            pass

        unrated.append(schemas.UnratedRideOut(
            ride_id=ride.id,
            request_id=req.id,
            driver_id=ride.driver_id,
            driver_name=f"{driver.first_name or ''} {driver.last_name or ''}".strip() if driver else "Driver",
            vehicle_number=vehicle_number,
            from_address=ride.from_address or "",
            to_address=ride.to_address or "",
            fare=ride.fare_per_seat or 0,
            completed_at=ride.created_at.isoformat() if ride.created_at else None,
        ))

    return unrated


@router.get("/driver/{driver_id}", response_model=schemas.DriverRatingStats)
def get_driver_rating(
    driver_id: int,
    db: Session = Depends(database.get_db),
):
    driver = db.query(models.User).filter(models.User.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    result = db.query(
        func.avg(models.Rating.stars).label("avg"),
        func.count(models.Rating.id).label("total"),
    ).filter(models.Rating.driver_id == driver_id).one()

    return schemas.DriverRatingStats(
        driver_id=driver_id,
        average_rating=round(float(result.avg or 0), 2),
        total_ratings=result.total,
    )


@router.get("/driver/{driver_id}/reviews", response_model=list[schemas.RatingOut])
def get_driver_reviews(
    driver_id: int,
    db: Session = Depends(database.get_db),
):
    return db.query(models.Rating).filter(models.Rating.driver_id == driver_id).order_by(models.Rating.created_at.desc()).all()


reviews_router = APIRouter(prefix="/reviews", tags=["Reviews"])

@reviews_router.post("/", response_model=schemas.RatingOut, status_code=status.HTTP_201_CREATED)
def submit_review(
    data: schemas.RatingCreate,
    db: Session = Depends(database.get_db),
    current_user=Depends(oauth2.get_current_user),
):
    return submit_rating(data, db, current_user)
