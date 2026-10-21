from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def make_dt(days_ago: int, hour: int, minute: int = 0) -> datetime:
    """Return a naive datetime in the past."""
    base = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    return base - timedelta(days=days_ago)


def seed_ride(db: Session, driver_id, vehicle_id, from_address, from_lat, from_lng,
              to_address, to_lat, to_lng, departure_time, seats_available=None,
              ac=None, fare_per_seat=0.0, gender_filter="any", status="completed"):
    ride = models.Ride(
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        from_address=from_address,
        from_lat=from_lat,
        from_lng=from_lng,
        to_address=to_address,
        to_lat=to_lat,
        to_lng=to_lng,
        departure_time=departure_time,
        seats_available=seats_available if seats_available is not None else 1,
        ac=ac,
        fare_per_seat=fare_per_seat,
        gender_filter=gender_filter,
        status=status,
    )
    db.add(ride)
    db.flush()
    return ride


def seed_request(db: Session, ride_id, passenger_id,
                 pickup_lat=None, pickup_lng=None, status="completed"):
    req = models.RideRequest(
        ride_id=ride_id,
        passenger_id=passenger_id,
        pickup_lat=pickup_lat,
        pickup_lng=pickup_lng,
        status=status,
        distance_from_route=0.0,
    )
    db.add(req)
    db.flush()
    return req


# ─────────────────────────────────────────────
#  KNOWN IDs
# ─────────────────────────────────────────────

# DRIVERS          user_id  vehicle_id  mode
# Hamza Nawaz        10        2        car
# Shiza Rajput       11        3        bike
# Faizan Nawaz       12        4        car   | 5  bike
# Sumaira Saeed      13        6        car
# Usman Awan         14        7        car   | 8  bike
# Fahad Zaidi        15        9        bike
# Waleed Mehmood      5       13        car   (also passenger)
# Sadia Mehmood       7       14        car   (also passenger)

# PASSENGERS  user_id
# Saad          1
# Zainab        2
# Sara          3
# Urooj         4
# Waleed        5   (also driver)
# Rabia         6
# Sadia         7   (also driver)
# Mustafa       8

# ─────────────────────────────────────────────
#  KARACHI AREA COORDINATES
# ─────────────────────────────────────────────
# DSU (destination for all uni rides)
DSU_ADDR   = "DHA Suffa University, Karachi"
DSU_LAT, DSU_LNG = 24.8607, 67.0011

# Pickup areas (passenger home areas)
GULSHAN    = ("Gulshan-e-Iqbal, Karachi",       24.9215, 67.0926)
NAZIMABAD  = ("Nazimabad, Karachi",              24.9200, 67.0350)
NORTH_NAZ  = ("North Nazimabad, Karachi",        24.9400, 67.0450)
GULISTAN   = ("Gulistan-e-Johar, Karachi",       24.9269, 67.1124)
CLIFTON    = ("Clifton, Karachi",                24.8138, 67.0300)
SADDAR     = ("Saddar, Karachi",                 24.8607, 67.0104)
PECHS      = ("PECHS, Karachi",                  24.8721, 67.0578)
MALIR      = ("Malir, Karachi",                  24.8935, 67.1946)
LANDHI     = ("Landhi, Karachi",                 24.8577, 67.2097)
FB_AREA    = ("F.B. Area, Karachi",              24.9308, 67.0653)


# ─────────────────────────────────────────────
#  MAIN SEED FUNCTION
# ─────────────────────────────────────────────

def run_seeds():
    db: Session = SessionLocal()
    try:

        # ══════════════════════════════════════
        # PATTERN 1 — Sara (3)
        # Every Monday & Wednesday ~9:45 AM
        # Gulshan → DSU   (Hamza car, vehicle 2)
        # ══════════════════════════════════════
        # past 4 weeks  →  days_ago for Mon/Wed
        sara_slots = [
            # (days_ago, hour, minute)
            (29, 9, 45),   # Mon  4 weeks ago
            (27, 9, 45),   # Wed
            (22, 9, 45),   # Mon  3 weeks ago
            (20, 9, 45),   # Wed
            (15, 9, 45),   # Mon  2 weeks ago
            (13, 9, 45),   # Wed
            (8,  9, 45),   # Mon  last week
            (6,  9, 45),   # Wed
        ]
        for days_ago, h, m in sara_slots:
            r = seed_ride(
                db,
                driver_id=10, vehicle_id=2,
                from_address=GULSHAN[0], from_lat=GULSHAN[1], from_lng=GULSHAN[2],
                to_address=DSU_ADDR,     to_lat=DSU_LAT,      to_lng=DSU_LNG,
                departure_time=make_dt(days_ago, h, m),
                seats_available=3, ac=True, fare_per_seat=150.0,
                gender_filter="any", status="completed",
            )
            seed_request(db, r.id, passenger_id=3,
                         pickup_lat=GULSHAN[1], pickup_lng=GULSHAN[2],
                         status="completed")

        # ══════════════════════════════════════
        # PATTERN 2 — Saad (1)
        # Every Tuesday & Thursday ~8:30 AM
        # Nazimabad → DSU   (Faizan car, vehicle 4)
        # ══════════════════════════════════════
        saad_slots = [
            (28, 8, 30),   # Tue  4 weeks ago
            (26, 8, 30),   # Thu
            (21, 8, 30),   # Tue  3 weeks ago
            (19, 8, 30),   # Thu
            (14, 8, 30),   # Tue  2 weeks ago
            (12, 8, 30),   # Thu
            (7,  8, 30),   # Tue  last week
            (5,  8, 30),   # Thu
        ]
        for days_ago, h, m in saad_slots:
            r = seed_ride(
                db,
                driver_id=12, vehicle_id=4,
                from_address=NAZIMABAD[0], from_lat=NAZIMABAD[1], from_lng=NAZIMABAD[2],
                to_address=DSU_ADDR,       to_lat=DSU_LAT,         to_lng=DSU_LNG,
                departure_time=make_dt(days_ago, h, m),
                seats_available=2, ac=False, fare_per_seat=120.0,
                gender_filter="any", status="completed",
            )
            seed_request(db, r.id, passenger_id=1,
                         pickup_lat=NAZIMABAD[1], pickup_lng=NAZIMABAD[2],
                         status="completed")

        # ══════════════════════════════════════
        # PATTERN 3 — Zainab (2)
        # Every Monday, Wednesday, Friday ~10:00 AM
        # Gulistan-e-Johar → DSU   (Sumaira car, vehicle 6)
        # gender_filter = female
        # ══════════════════════════════════════
        zainab_slots = [
            (29, 10, 0),   # Mon
            (27, 10, 0),   # Wed
            (25, 10, 0),   # Fri
            (22, 10, 0),
            (20, 10, 0),
            (18, 10, 0),
            (15, 10, 0),
            (13, 10, 0),
            (11, 10, 0),
            (8,  10, 0),
            (6,  10, 0),
            (4,  10, 0),
        ]
        for days_ago, h, m in zainab_slots:
            r = seed_ride(
                db,
                driver_id=13, vehicle_id=6,
                from_address=GULISTAN[0], from_lat=GULISTAN[1], from_lng=GULISTAN[2],
                to_address=DSU_ADDR,      to_lat=DSU_LAT,        to_lng=DSU_LNG,
                departure_time=make_dt(days_ago, h, m),
                seats_available=2, ac=True, fare_per_seat=100.0,
                gender_filter="female", status="completed",
            )
            seed_request(db, r.id, passenger_id=2,
                         pickup_lat=GULISTAN[1], pickup_lng=GULISTAN[2],
                         status="completed")

        # ══════════════════════════════════════
        # PATTERN 4 — Urooj (4)
        # Every Tuesday & Friday ~11:00 AM
        # North Nazimabad → DSU   (Usman car, vehicle 7)
        # ══════════════════════════════════════
        urooj_slots = [
            (28, 11, 0),
            (25, 11, 0),
            (21, 11, 0),
            (18, 11, 0),
            (14, 11, 0),
            (11, 11, 0),
            (7,  11, 0),
            (4,  11, 0),
        ]
        for days_ago, h, m in urooj_slots:
            r = seed_ride(
                db,
                driver_id=14, vehicle_id=7,
                from_address=NORTH_NAZ[0], from_lat=NORTH_NAZ[1], from_lng=NORTH_NAZ[2],
                to_address=DSU_ADDR,        to_lat=DSU_LAT,         to_lng=DSU_LNG,
                departure_time=make_dt(days_ago, h, m),
                seats_available=3, ac=True, fare_per_seat=130.0,
                gender_filter="any", status="completed",
            )
            seed_request(db, r.id, passenger_id=4,
                         pickup_lat=NORTH_NAZ[1], pickup_lng=NORTH_NAZ[2],
                         status="completed")

        # ══════════════════════════════════════
        # PATTERN 5 — Rabia (6)
        # Every Monday & Thursday ~8:00 AM
        # PECHS → DSU   (Waleed car, vehicle 13)
        # ══════════════════════════════════════
        rabia_slots = [
            (29, 8, 0),
            (26, 8, 0),
            (22, 8, 0),
            (19, 8, 0),
            (15, 8, 0),
            (12, 8, 0),
            (8,  8, 0),
            (5,  8, 0),
        ]
        for days_ago, h, m in rabia_slots:
            r = seed_ride(
                db,
                driver_id=5, vehicle_id=13,
                from_address=PECHS[0], from_lat=PECHS[1], from_lng=PECHS[2],
                to_address=DSU_ADDR,   to_lat=DSU_LAT,    to_lng=DSU_LNG,
                departure_time=make_dt(days_ago, h, m),
                seats_available=2, ac=False, fare_per_seat=110.0,
                gender_filter="any", status="completed",
            )
            seed_request(db, r.id, passenger_id=6,
                         pickup_lat=PECHS[1], pickup_lng=PECHS[2],
                         status="completed")

        # ══════════════════════════════════════
        # PATTERN 6 — Mustafa (8)
        # Every Wednesday & Saturday ~9:00 AM
        # FB Area → DSU   (Faizan bike, vehicle 5)
        # ══════════════════════════════════════
        mustafa_slots = [
            (27, 9, 0),
            (24, 9, 0),
            (20, 9, 0),
            (17, 9, 0),
            (13, 9, 0),
            (10, 9, 0),
            (6,  9, 0),
            (3,  9, 0),
        ]
        for days_ago, h, m in mustafa_slots:
            r = seed_ride(
                db,
                driver_id=12, vehicle_id=5,
                from_address=FB_AREA[0], from_lat=FB_AREA[1], from_lng=FB_AREA[2],
                to_address=DSU_ADDR,     to_lat=DSU_LAT,      to_lng=DSU_LNG,
                departure_time=make_dt(days_ago, h, m),
                seats_available=1, ac=None, fare_per_seat=80.0,
                gender_filter="any", status="completed",
            )
            seed_request(db, r.id, passenger_id=8,
                         pickup_lat=FB_AREA[1], pickup_lng=FB_AREA[2],
                         status="completed")

        # ══════════════════════════════════════
        # PATTERN 7 — Waleed (5) as PASSENGER
        # Every Tuesday & Thursday ~7:45 AM
        # Malir → DSU   (Usman bike, vehicle 8)
        # ══════════════════════════════════════
        waleed_slots = [
            (28, 7, 45),
            (26, 7, 45),
            (21, 7, 45),
            (19, 7, 45),
            (14, 7, 45),
            (12, 7, 45),
            (7,  7, 45),
            (5,  7, 45),
        ]
        for days_ago, h, m in waleed_slots:
            r = seed_ride(
                db,
                driver_id=14, vehicle_id=8,
                from_address=MALIR[0], from_lat=MALIR[1], from_lng=MALIR[2],
                to_address=DSU_ADDR,   to_lat=DSU_LAT,    to_lng=DSU_LNG,
                departure_time=make_dt(days_ago, h, m),
                seats_available=1, ac=None, fare_per_seat=90.0,
                gender_filter="any", status="completed",
            )
            seed_request(db, r.id, passenger_id=5,
                         pickup_lat=MALIR[1], pickup_lng=MALIR[2],
                         status="completed")

        # ══════════════════════════════════════
        # PATTERN 8 — Sadia (7) as PASSENGER
        # Every Monday & Wednesday ~10:30 AM
        # Clifton → DSU   (Shiza bike, vehicle 3)
        # gender_filter = female
        # ══════════════════════════════════════
        sadia_slots = [
            (29, 10, 30),
            (27, 10, 30),
            (22, 10, 30),
            (20, 10, 30),
            (15, 10, 30),
            (13, 10, 30),
            (8,  10, 30),
            (6,  10, 30),
        ]
        for days_ago, h, m in sadia_slots:
            r = seed_ride(
                db,
                driver_id=11, vehicle_id=3,
                from_address=CLIFTON[0], from_lat=CLIFTON[1], from_lng=CLIFTON[2],
                to_address=DSU_ADDR,     to_lat=DSU_LAT,      to_lng=DSU_LNG,
                departure_time=make_dt(days_ago, h, m),
                seats_available=1, ac=None, fare_per_seat=100.0,
                gender_filter="female", status="completed",
            )
            seed_request(db, r.id, passenger_id=7,
                         pickup_lat=CLIFTON[1], pickup_lng=CLIFTON[2],
                         status="completed")

        # ══════════════════════════════════════
        # EXTRA VARIETY RIDES
        # (Fahad Zaidi bike, Hamza car, Sumaira car)
        # so drivers have diverse history too
        # ══════════════════════════════════════

        # Fahad (15, bike 9) — Saddar → DSU  various days
        fahad_extra = [
            (30, 8, 0), (23, 8, 0), (16, 8, 0), (9, 8, 0), (2, 8, 0)
        ]
        for days_ago, h, m in fahad_extra:
            seed_ride(
                db,
                driver_id=15, vehicle_id=9,
                from_address=SADDAR[0], from_lat=SADDAR[1], from_lng=SADDAR[2],
                to_address=DSU_ADDR,    to_lat=DSU_LAT,     to_lng=DSU_LNG,
                departure_time=make_dt(days_ago, h, m),
                seats_available=1, ac=None, fare_per_seat=70.0,
                gender_filter="any", status="completed",
            )

        # Hamza (10, car 2) — Landhi → DSU extra rides (no passenger — solo)
        hamza_extra = [
            (25, 9, 0), (18, 9, 0), (11, 9, 0), (4, 9, 0)
        ]
        for days_ago, h, m in hamza_extra:
            seed_ride(
                db,
                driver_id=10, vehicle_id=2,
                from_address=LANDHI[0], from_lat=LANDHI[1], from_lng=LANDHI[2],
                to_address=DSU_ADDR,    to_lat=DSU_LAT,     to_lng=DSU_LNG,
                departure_time=make_dt(days_ago, h, m),
                seats_available=3, ac=True, fare_per_seat=160.0,
                gender_filter="any", status="completed",
            )

        # Sumaira (13, car 6) — Malir → DSU extra rides
        sumaira_extra = [
            (26, 10, 0), (19, 10, 0), (12, 10, 0), (5, 10, 0)
        ]
        for days_ago, h, m in sumaira_extra:
            seed_ride(
                db,
                driver_id=13, vehicle_id=6,
                from_address=MALIR[0], from_lat=MALIR[1], from_lng=MALIR[2],
                to_address=DSU_ADDR,   to_lat=DSU_LAT,    to_lng=DSU_LNG,
                departure_time=make_dt(days_ago, h, m),
                seats_available=2, ac=True, fare_per_seat=140.0,
                gender_filter="female", status="completed",
            )

        # Sadia (7, car 14) as DRIVER — Clifton → DSU extra rides
        sadia_driver_extra = [
            (24, 10, 30), (17, 10, 30), (10, 10, 30), (3, 10, 30)
        ]
        for days_ago, h, m in sadia_driver_extra:
            seed_ride(
                db,
                driver_id=7, vehicle_id=14,
                from_address=CLIFTON[0], from_lat=CLIFTON[1], from_lng=CLIFTON[2],
                to_address=DSU_ADDR,     to_lat=DSU_LAT,      to_lng=DSU_LNG,
                departure_time=make_dt(days_ago, h, m),
                seats_available=2, ac=True, fare_per_seat=100.0,
                gender_filter="female", status="completed",
            )

        db.commit()
        print("✅ Seeds inserted successfully!")
        print("   Rides + RideRequests created with realistic Karachi patterns.")

    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seeds()
