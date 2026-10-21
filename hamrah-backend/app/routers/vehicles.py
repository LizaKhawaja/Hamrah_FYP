from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, oauth2
from ..database import get_db

router = APIRouter(
    prefix="/vehicles",
    tags=["Vehicles"]
)

#list all vehicles of a driver
@router.get("/", response_model=list[schemas.VehicleOut])
def list_vehicles(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if not current_user.is_driver:
        raise HTTPException(
            status_code=403,
            detail="Driver role required"
        )

    return current_user.vehicles or []

#add new vehicle
@router.post("/", response_model=schemas.VehicleOut, status_code=201)
def add_vehicle(
    vehicle: schemas.VehicleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if not current_user.is_driver:
        raise HTTPException(
            status_code=403,
            detail="Driver role required"
        )

    existing = current_user.vehicles or []

    if len(existing) >= 2:
        raise HTTPException(
            status_code=400,
            detail="Maximum 2 vehicles allowed"
        )

    if db.query(models.Vehicle).filter(
        models.Vehicle.vehicle_number == vehicle.vehicle_number
    ).first():
        raise HTTPException(
            status_code=400,
            detail=f"Vehicle already registered: {vehicle.vehicle_number}"
        )

    new_vehicle = models.Vehicle(
        user_id=current_user.id,
        vehicle_number=vehicle.vehicle_number,
        mode_of_transport=vehicle.mode_of_transport,
        vehicle_model=vehicle.vehicle_model,
        vehicle_colour=vehicle.vehicle_colour,
    )

    db.add(new_vehicle)
    db.commit()
    db.refresh(new_vehicle)

    return new_vehicle

#add, update and delete vehicle. Sync list
@router.put("/sync", response_model=list[schemas.VehicleOut])
def sync_vehicles(
    vehicles: list[schemas.VehicleCreateWithId],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if not current_user.is_driver:
        raise HTTPException(
            status_code=403,
            detail="Driver role required"
        )

    if len(vehicles) > 2:
        raise HTTPException(
            status_code=400,
            detail="Maximum 2 vehicles allowed"
        )

    existing_vehicles = db.query(models.Vehicle).filter(
        models.Vehicle.user_id == current_user.id
    ).all()

    existing_map = {
        vehicle.id: vehicle
        for vehicle in existing_vehicles
    }

    incoming_ids = set()

    for vehicle_data in vehicles:

        duplicate = db.query(models.Vehicle).filter(
            models.Vehicle.vehicle_number ==
            vehicle_data.vehicle_number
        ).first()

        if duplicate and (
            vehicle_data.id is None or
            duplicate.id != vehicle_data.id
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Vehicle already registered: {vehicle_data.vehicle_number}"
            )

        if (
            vehicle_data.id is not None and
            vehicle_data.id in existing_map
        ):

            vehicle = existing_map[vehicle_data.id]

            vehicle.vehicle_number = vehicle_data.vehicle_number
            vehicle.mode_of_transport = vehicle_data.mode_of_transport
            vehicle.vehicle_model = vehicle_data.vehicle_model
            vehicle.vehicle_colour = vehicle_data.vehicle_colour

            incoming_ids.add(vehicle.id)

        else:

            new_vehicle = models.Vehicle(
                user_id=current_user.id,
                vehicle_number=vehicle_data.vehicle_number,
                mode_of_transport=vehicle_data.mode_of_transport,
                vehicle_model=vehicle_data.vehicle_model,
                vehicle_colour=vehicle_data.vehicle_colour,
            )

            db.add(new_vehicle)
            db.flush()

            incoming_ids.add(new_vehicle.id)

    for vehicle in existing_vehicles:

        if vehicle.id not in incoming_ids:

            active_ride = db.query(models.Ride).filter(
                models.Ride.driver_id == current_user.id,
                models.Ride.vehicle_id == vehicle.id,
                models.Ride.status.in_(
                    ["active", "full", "ongoing"]
                ),
            ).first()

            if active_ride:
                continue

            db.delete(vehicle)

    db.commit()

    return db.query(models.Vehicle).filter(
        models.Vehicle.user_id == current_user.id
    ).all()


#delete a specific vehicle
@router.delete("/{vehicle_id}")
def remove_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.id == vehicle_id,
        models.Vehicle.user_id == current_user.id,
    ).first()

    if not vehicle:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found"
        )

    active_ride = db.query(models.Ride).filter(
        models.Ride.driver_id == current_user.id,
        models.Ride.vehicle_id == vehicle_id,
        models.Ride.status.in_(
            ["active", "full", "ongoing"]
        ),
    ).first()

    if active_ride:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove vehicle used by an active ride"
        )

    db.delete(vehicle)
    db.commit()

    return {
        "message": "Vehicle removed",
        "vehicle_id": vehicle_id
    }
