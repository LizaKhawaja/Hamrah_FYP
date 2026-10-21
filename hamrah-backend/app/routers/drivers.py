from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas, utils, oauth2
from ..database import get_db
from ..services import mail_service

router = APIRouter(prefix="/drivers", tags=["Drivers"])

#min 1 and max 2 vehicles can be registered and no duplicate vehicle number
def _validate_vehicles(db: Session, vehicles: list[schemas.VehicleCreate], user_id: int | None = None):
    if not vehicles:
        raise HTTPException(status_code=400, detail="At least 1 vehicle is required")
    if len(vehicles) > 2:
        raise HTTPException(status_code=400, detail="Maximum 2 vehicles allowed")

    numbers = [v.vehicle_number for v in vehicles]
    if len(numbers) != len(set(numbers)):
        raise HTTPException(status_code=400, detail="Duplicate vehicle numbers in request")

    for v in vehicles:
        existing = db.query(models.Vehicle).filter(
            models.Vehicle.vehicle_number == v.vehicle_number
        ).first()
        if existing and existing.user_id != user_id:
            raise HTTPException(
                status_code=400,
                detail=f"Vehicle already registered: {v.vehicle_number}",
            )

#passenger becomes driver (switch mode from passenger to driver)
@router.post("/register")
def register_driver(
    payload: schemas.DriverEnable,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if current_user.dsu_reg_id != payload.dsu_reg_id:
        raise HTTPException(status_code=400, detail="DSU Registration ID mismatch")

    if current_user.is_driver and current_user.is_verified:
        raise HTTPException(status_code=400, detail="Driver role already enabled")

    _validate_vehicles(db, payload.vehicles, current_user.id)

    otp_code = utils.generate_otp()
    otp_expiry = utils.otp_expiry_time()
    mail_service.send_otp_email(current_user.email, otp_code)

    current_user.is_driver = True
    current_user.is_passenger = True
    current_user.role = "driver"
    current_user.nic_image_url = payload.cnic_image_url
    current_user.live_image_url = payload.live_image_url
    current_user.license_image_url = payload.license_image_url
    current_user.is_verified = False
    current_user.otp_code = otp_code
    current_user.otp_expiry = otp_expiry

    db.flush()

    for v in payload.vehicles:
        if not v.vehicle_colour or not v.vehicle_model:
            raise HTTPException(
                status_code=400,
                detail=f"Missing vehicle data: {v.vehicle_number}",
            )
        db.add(models.Vehicle(
            user_id=current_user.id,
            vehicle_number=v.vehicle_number,
            mode_of_transport=v.mode_of_transport,
            vehicle_model=v.vehicle_model,
            vehicle_colour=v.vehicle_colour,
        ))

    db.commit()
    db.refresh(current_user)

    return {
        "message": "Driver registration started. OTP sent to email.",
        "vehicles_registered": len(payload.vehicles),
        "user_id": current_user.id,
        "email": current_user.email,
    }
