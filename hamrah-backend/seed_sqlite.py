"""Seed SQLite test database with DSU students and demo users."""
import csv
import os
from datetime import datetime, timedelta

from app.database import Base, SessionLocal, engine
from app import models, utils

CSV_PATH = os.path.join(os.path.dirname(__file__), "students.csv")
TEST_PASSWORD = "Test1234!"


def load_students(db):
    if db.query(models.DSUStudent).count() > 0:
        return

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            reg_id = (row.get("dsu_reg_id.") or row.get("dsu_reg_id") or "").strip()
            if not reg_id:
                continue
            db.add(
                models.DSUStudent(
                    full_name=row.get("full_name", "").strip(),
                    dsu_reg_id=reg_id,
                    department=row.get("department", "").strip() or None,
                    gender=row.get("gender", "").strip() or None,
                    email=row.get("email", "").strip() or None,
                )
            )
    db.commit()
    print(f"Loaded {db.query(models.DSUStudent).count()} DSU students")


def upsert_user(db, *, dsu_reg_id, first_name, last_name, email, phone, gender,
                is_passenger, is_driver, role, verified=True):
    user = db.query(models.User).filter(models.User.dsu_reg_id == dsu_reg_id).first()
    if user:
        return user

    user = models.User(
        first_name=first_name,
        last_name=last_name,
        dsu_reg_id=dsu_reg_id,
        phone_number=phone,
        email=email,
        password=utils.hash_pass(TEST_PASSWORD),
        gender=gender,
        is_passenger=is_passenger,
        is_driver=is_driver,
        role=role,
        nic_image_url="http://127.0.0.1:8000/uploads/test_cnic.jpg",
        live_image_url="http://127.0.0.1:8000/uploads/test_live.jpg",
        license_image_url="http://127.0.0.1:8000/uploads/test_license.jpg",
        is_verified=verified,
    )
    db.add(user)
    db.flush()
    return user


def seed_demo_users(db):
    passenger = upsert_user(
        db,
        dsu_reg_id="cs232322",
        first_name="Bushra",
        last_name="Ahmed",
        email="bushra.ahmed@gmail.com",
        phone="03001111111",
        gender="female",
        is_passenger=True,
        is_driver=False,
        role="passenger",
    )

    driver = upsert_user(
        db,
        dsu_reg_id="cs231830",
        first_name="Hamza",
        last_name="Nawaz",
        email="hamza.nawaz@gmail.com",
        phone="03002222222",
        gender="male",
        is_passenger=False,
        is_driver=True,
        role="driver",
    )

    vehicle = db.query(models.Vehicle).filter(models.Vehicle.user_id == driver.id).first()
    if not vehicle:
        vehicle = models.Vehicle(
            user_id=driver.id,
            vehicle_number="KHI-1234",
            mode_of_transport="car",
            vehicle_model="Corolla",
            vehicle_colour="White",
        )
        db.add(vehicle)
        db.flush()

    future = datetime.utcnow() + timedelta(days=1)
    ride = db.query(models.Ride).filter(models.Ride.driver_id == driver.id).first()
    if not ride:
        ride = models.Ride(
            driver_id=driver.id,
            vehicle_id=vehicle.id,
            from_address="DSU Campus, Karachi",
            from_lat=24.8607,
            from_lng=67.0011,
            to_address="Saddar, Karachi",
            to_lat=24.8600,
            to_lng=67.0100,
            departure_time=future,
            seats_available=3,
            ac=True,
            gender_filter="any",
            fare_per_seat=150.0,
            status="active",
        )
        db.add(ride)
    else:
        ride.status = "active"
        ride.seats_available = 3
        ride.departure_time = future

    db.query(models.RideRequest).filter(models.RideRequest.ride_id == ride.id).delete()
    db.query(models.Rating).filter(models.Rating.ride_id == ride.id).delete()
    db.query(models.ChatMessage).filter(models.ChatMessage.ride_id == ride.id).delete()

    db.commit()
    print(f"Demo passenger: {passenger.dsu_reg_id} / {TEST_PASSWORD}")
    print(f"Demo driver:    {driver.dsu_reg_id} / {TEST_PASSWORD}")
    print(f"Demo ride id:   {ride.id if ride else 'n/a'}")


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        load_students(db)
        seed_demo_users(db)
    finally:
        db.close()
    print("SQLite seed complete.")


if __name__ == "__main__":
    main()
