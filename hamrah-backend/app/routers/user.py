from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime
import os, uuid
import requests
from .. import models, schemas, utils, oauth2
from ..database import get_db
from ..services import mail_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=schemas.MeOut)
def get_me(current_user: models.User = Depends(oauth2.get_current_user),
           db: Session = Depends(get_db)):
    driver_profile_complete = bool(
        current_user.is_driver and
        current_user.nic_image_url and
        current_user.live_image_url and
        current_user.license_image_url
    )

    return schemas.MeOut(
        id=current_user.id,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        dsu_reg_id=current_user.dsu_reg_id,
        phone_number=current_user.phone_number,
        email=current_user.email,
        gender=current_user.gender,
        is_passenger=current_user.is_passenger,
        is_driver=current_user.is_driver,
        active_mode=current_user.role,
        driver_profile_complete=driver_profile_complete,
        vehicles=[
            schemas.VehicleOut(
                id=v.id,
                vehicle_number=v.vehicle_number,
                mode_of_transport=v.mode_of_transport,
                vehicle_model=v.vehicle_model,
                vehicle_colour=v.vehicle_colour,
            ) for v in current_user.vehicles
        ] if current_user.vehicles else [],
        total_rides=db.query(models.Ride).filter(
            models.Ride.driver_id == current_user.id,
            models.Ride.status == 'completed'
        ).count()
    )


#update user's profile
@router.patch("/profile")
def update_profile(
    payload: schemas.ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    if payload.first_name: current_user.first_name = payload.first_name
    if payload.last_name:  current_user.last_name  = payload.last_name
    if payload.phone_number: current_user.phone_number = payload.phone_number
    db.commit()
    return {"message": "Profile updated successfully"}


#driver to passenger switch (only mode switch)
@router.patch("/switch-mode")
def switch_mode(
    payload: schemas.SwitchMode,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    if payload.mode == "driver" and not current_user.is_driver:
        raise HTTPException(status_code=400, detail="You are not a driver yet. Enable driver mode first.")

    if payload.mode == "passenger" and not current_user.is_passenger:
        raise HTTPException(status_code=400, detail="Passenger role not enabled.")

    current_user.role = payload.mode
    db.commit()
    db.refresh(current_user)

    return {"message": f"Switched to {payload.mode} mode"}


#enable passenger role for driver
@router.post("/enable_passenger")
def enable_passenger(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if not current_user.is_driver:
        raise HTTPException(status_code=400, detail="Driver account required")
    if current_user.is_passenger:
        return {"message": "Passenger mode already enabled"}
    current_user.is_passenger = True
    db.commit()
    return {"message": "Passenger mode enabled"}


# Passanger signup
@router.post("/passenger", response_model=schemas.UserOut)
def create_passenger(user: schemas.PassengerCreate, db: Session = Depends(get_db)):

    student = db.query(models.DSUStudent).filter_by(dsu_reg_id=user.dsu_reg_id).first()
    if not student:
        raise HTTPException(status_code=400, detail="Invalid DSU Registration ID")

    existing = db.query(models.User).filter(models.User.dsu_reg_id == user.dsu_reg_id).first()
    if existing:
        if existing.is_driver and not existing.is_passenger:
            existing.is_passenger = True
            otp_code = utils.generate_otp()
            otp_expiry = utils.otp_expiry_time()
            mail_service.send_otp_email(existing.email, otp_code)
            existing.otp_code = otp_code
            existing.otp_expiry = otp_expiry
            existing.is_verified = False
            db.commit()
            return existing
        raise HTTPException(status_code=400, detail="DSU Registration ID already registered")

    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")

    if db.query(models.User).filter(models.User.phone_number == user.phone_number).first():
        raise HTTPException(status_code=400, detail="Phone number already exists")

    hashed_password = utils.hash_pass(user.password)

    otp_code = utils.generate_otp()
    otp_expiry = utils.otp_expiry_time()
    mail_service.send_otp_email(user.email, otp_code)
    print(f"[OTP] {user.email} -> {otp_code}")

    user_data = user.model_dump(exclude={"password"})

    new_user = models.User(
        **user_data,
        password=hashed_password,
        is_passenger=True,
        is_driver=False,
        role="passenger",
        is_verified=False,
        otp_code=otp_code,
        otp_expiry=otp_expiry
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# Download image
def download_image(url: str, save_path: str):

    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid image URL")

    try:
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Unable to download image")

        with open(save_path, "wb") as f:
            f.write(response.content)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image download error: {str(e)}")


# Driver signup
@router.post("/driver")
def create_driver(driver: schemas.DriverCreate, db: Session = Depends(get_db)):

    student = db.query(models.DSUStudent).filter_by(dsu_reg_id=driver.dsu_reg_id).first()
    if not student:
        print(f"[DRIVER REG] FAIL: Invalid DSU ID = {driver.dsu_reg_id}")
        raise HTTPException(status_code=400, detail="Invalid DSU Registration ID")

    # user uniqueness
    if db.query(models.User).filter(models.User.dsu_reg_id == driver.dsu_reg_id).first():
        print(f"[DRIVER REG] Already passenger → switching to enable_driver for {driver.dsu_reg_id}")
        raise HTTPException(status_code=400, detail="DSU Registration ID already registered")

    if db.query(models.User).filter(models.User.email == driver.email).first():
        print(f"[DRIVER REG] FAIL: Email already exists = {driver.email}")
        raise HTTPException(status_code=400, detail="Email already exists")

    if db.query(models.User).filter(models.User.phone_number == driver.phone_number).first():
        print(f"[DRIVER REG] FAIL: Phone already exists = {driver.phone_number}")
        raise HTTPException(status_code=400, detail="Phone number already exists")

    # vehicles validation
    if not driver.vehicles or len(driver.vehicles) == 0:
        raise HTTPException(status_code=400, detail="At least 1 vehicle is required")

    if len(driver.vehicles) > 2:
        raise HTTPException(status_code=400, detail="Maximum 2 vehicles allowed")

    req_vehicle_numbers = [v.vehicle_number for v in driver.vehicles]
    if len(req_vehicle_numbers) != len(set(req_vehicle_numbers)):
        raise HTTPException(status_code=400, detail="Duplicate vehicle numbers in request")

    for v in driver.vehicles:
        if db.query(models.Vehicle).filter(models.Vehicle.vehicle_number == v.vehicle_number).first():
            raise HTTPException(status_code=400, detail=f"Vehicle already registered: {v.vehicle_number}")

    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    otp_code = utils.generate_otp()
    otp_expiry = utils.otp_expiry_time()
    mail_service.send_otp_email(driver.email, otp_code)

    hashed_password = utils.hash_pass(driver.password)

    user_obj = models.User(
        first_name=driver.first_name,
        last_name=driver.last_name,
        dsu_reg_id=driver.dsu_reg_id,
        phone_number=driver.phone_number,
        email=driver.email.lower(),
        password=hashed_password,
        gender=driver.gender,
        nic_image_url=driver.cnic_image_url,
        live_image_url=driver.live_image_url,
        license_image_url=driver.license_image_url,
        is_passenger=False,  
        is_driver=True,
        role="driver",
        is_verified=False,
        otp_code=otp_code,
        otp_expiry=otp_expiry
    )

    db.add(user_obj)
    db.flush()

    for v in driver.vehicles:
        db.add(models.Vehicle(
            user_id=user_obj.id,
            vehicle_number=v.vehicle_number,
            mode_of_transport=v.mode_of_transport,
            vehicle_model=v.vehicle_model,
            vehicle_colour=v.vehicle_colour      
        ))

    db.commit()
    db.refresh(user_obj)

    return {
        "message": "Driver signup successful. OTP sent to email.",
        "face_distance": None,
        "vehicles_registered": len(driver.vehicles),
        "user_id": user_obj.id
    }

#convert passenger account into driver
@router.post("/enable_driver")
def enable_driver(payload: schemas.DriverEnable, db: Session = Depends(get_db)):
    student = db.query(models.DSUStudent).filter_by(dsu_reg_id=payload.dsu_reg_id).first()
    if not student:
        raise HTTPException(status_code=400, detail="Invalid DSU Registration ID")

    existing_user = db.query(models.User).filter(models.User.dsu_reg_id == payload.dsu_reg_id).first()
    if not existing_user:
        raise HTTPException(status_code=400, detail="User must signup as passenger first")

    if existing_user.is_driver and existing_user.is_verified:
        print(f"[ENABLE DRIVER] FAIL: already driver = {payload.dsu_reg_id}")
        raise HTTPException(status_code=400, detail="Driver role already enabled for this account")

    if not payload.vehicles or len(payload.vehicles) == 0:
        print(f"[ENABLE DRIVER] FAIL: no vehicles")
        raise HTTPException(status_code=400, detail="At least 1 vehicle is required")

    if len(payload.vehicles) > 2:
        raise HTTPException(status_code=400, detail="Maximum 2 vehicles allowed")

    req_vehicle_numbers = [v.vehicle_number for v in payload.vehicles]
    if len(req_vehicle_numbers) != len(set(req_vehicle_numbers)):
        raise HTTPException(status_code=400, detail="Duplicate vehicle numbers in request")

    for v in payload.vehicles:
        if db.query(models.Vehicle).filter(models.Vehicle.vehicle_number == v.vehicle_number).first():
            print(f"[ENABLE DRIVER] FAIL: vehicle already registered = {v.vehicle_number}")
            raise HTTPException(status_code=400, detail=f"Vehicle already registered: {v.vehicle_number}")

    otp_code = utils.generate_otp()
    otp_expiry = utils.otp_expiry_time()
    otp_email = payload.email if payload.email else existing_user.email
    mail_service.send_otp_email(otp_email, otp_code)

    existing_user.is_driver = True
    existing_user.is_passenger = True
    existing_user.role = "driver"

    existing_user.nic_image_url = payload.cnic_image_url
    existing_user.live_image_url = payload.live_image_url
    existing_user.license_image_url = payload.license_image_url

    existing_user.is_verified = False
    existing_user.otp_code = otp_code
    existing_user.otp_expiry = otp_expiry

    db.flush()

    for v in payload.vehicles:
     if not v.vehicle_colour or not v.vehicle_model:
        raise HTTPException(status_code=400, detail=f"Missing vehicle data: {v.vehicle_number}")

    for v in payload.vehicles:
     db.add(models.Vehicle(
        user_id=existing_user.id,
        vehicle_number=v.vehicle_number,
        mode_of_transport=v.mode_of_transport,
        vehicle_model=v.vehicle_model,
        vehicle_colour=v.vehicle_colour
    ))

    db.commit()
    db.refresh(existing_user)

    return {
        "message": "Driver mode enabled successfully. OTP sent to email.",
        "face_distance": None,
        "vehicles_registered": len(payload.vehicles),
        "user_id": existing_user.id,
        "email": existing_user.email,
    }

# VERIFY OTP
@router.post("/verify-otp")
def verify_otp(data: schemas.OTPVerify, db: Session = Depends(get_db)):

    user = db.query(models.User).filter(models.User.email == data.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="User already verified")

    if user.otp_code != data.otp_code:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if user.otp_expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired")

    user.is_verified = True
    user.otp_code = None
    user.otp_expiry = None

    db.commit()

    return {"message": "Account verified successfully"}

# RESEND OTP
@router.post("/resend-otp")
def resend_otp(data: schemas.ResendOTP, db: Session = Depends(get_db)):

    user = db.query(models.User).filter(models.User.email == data.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="User already verified")

    new_otp = utils.generate_otp()

    user.otp_code = new_otp
    user.otp_expiry = utils.otp_expiry_time()

    mail_service.send_otp_email(user.email, new_otp)
    print(f"[OTP] {user.email} -> {new_otp}")

    db.commit()

    return {"message": "New OTP sent successfully"}