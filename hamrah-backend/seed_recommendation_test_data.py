"""
seed_recommendation_test_data.py

Seeds test data for the Hamrah AI ride-recommendation feature so it can be
tested via POST /recommendations/test-run without waiting for real usage.

WHAT THIS SCRIPT DOES
----------------------
For 7 existing passenger users, it inserts:
  1. Past "completed" Rides + "dropped" RideRequests (last ~30 days) that
     establish weekday patterns (some multi-weekday, some single, some
     deliberately NOT a pattern).
  2. One shared "buffer" ride (2 days ago) linked to all 7 passengers, so
     none of them get filtered out by the 7-day recency gate inside
     get_ride_history_summary() before the 30-day pattern logic even runs.
  3. Fake DeviceToken rows for all 7 passengers, because run_recommendations()
     only considers passengers who have at least one device token.

For 5 existing driver users, it inserts:
  1. Future "active" Rides — some deliberately matching a passenger's
     pattern (positive test), some deliberately NOT matching (distance/time
     negative tests), and one where a driver posts a ride matching their
     OWN passenger-side pattern (self-exclusion sanity check).

IMPORTANT
---------
- This script assumes users, vehicles are ALREADY created in the DB
  (per your existing setup) — it does NOT create Users or Vehicles.
- All dates are computed relative to datetime.now() at run time, so you
  can run this script on any day and get correctly "recent" / "future"
  dates — nothing is hardcoded to a specific calendar date.
- Run this from your backend project root (where the `app` package lives),
  e.g.:  python seed_recommendation_test_data.py
"""

from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import Ride, RideRequest, DeviceToken

# ──────────────────────────────────────────────────────────────────
# Reference user IDs (already exist in your DB — not created here)
# ──────────────────────────────────────────────────────────────────
BUSHRA_ID  = 1   # passenger — multi-weekday pattern (Mon + Wed)
ZEESHAN_ID = 2   # passenger — only 1 ride ever (threshold test)
MINAL_ID   = 3   # passenger + driver — self-exclusion sanity check
AQSA_ID    = 4   # passenger — random/inconsistent days (no pattern)
ARNAV_ID   = 5   # passenger — pattern exists, future ride time-mismatch
ASAD_ID    = 6   # passenger — evening pattern, positive case
POOJA_ID   = 7   # passenger — pattern exists, but no matching future ride

JUNAID_ID  = 8   # driver, vehicle 1, car
ZAINAB_ID  = 9   # driver, vehicle 2, car
MAHESH_ID  = 10  # driver, vehicle 4, car
HAROON_ID  = 11  # driver, vehicle 5, bike
ALI_ID     = 12  # driver, vehicle 6, bike

VEHICLE_OF = {
    JUNAID_ID: 1,
    ZAINAB_ID: 2,
    MINAL_ID:  3,
    MAHESH_ID: 4,
    HAROON_ID: 5,
    ALI_ID:    6,
}
BIKE_DRIVERS = {HAROON_ID, ALI_ID}  # seats_available must be 1 for bikes

# ──────────────────────────────────────────────────────────────────
# Coordinates (approximate — good enough for testing, not precision geocoding)
# ──────────────────────────────────────────────────────────────────
DSU        = (24.81469, 67.08002)
NAZIMABAD  = (24.9067, 67.0345)   # Ziauddin Chowrangi
CLIFTON    = (24.8138, 67.0299)   # 2 Talwar
FB_AREA    = (24.9280, 67.0663)
JOHAR_16   = (24.9180, 67.1280)
GULSHAN    = (24.9200, 67.0996)
SADDAR     = (24.8547, 67.0207)
GARDEN_E   = (24.8695, 67.0280)


# ──────────────────────────────────────────────────────────────────
# Date helpers — everything is relative to "now", not hardcoded
# ──────────────────────────────────────────────────────────────────
def most_recent_weekday(now: datetime, target_weekday: int, weeks_ago: int = 0) -> datetime:
    """Most recent PAST occurrence of target_weekday (0=Mon..6=Sun),
    then step back `weeks_ago` additional weeks. Always strictly in the past."""
    days_since = (now.weekday() - target_weekday) % 7
    if days_since == 0:
        days_since = 7
    base = now - timedelta(days=days_since)
    return base - timedelta(weeks=weeks_ago)


def next_weekday(now: datetime, target_weekday: int, weeks_ahead: int = 0) -> datetime:
    """Next FUTURE occurrence of target_weekday, then step forward
    `weeks_ahead` additional weeks. Always strictly in the future."""
    days_ahead = (target_weekday - now.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    base = now + timedelta(days=days_ahead)
    return base + timedelta(weeks=weeks_ahead)


def at(d: datetime, hour: int, minute: int = 0) -> datetime:
    return d.replace(hour=hour, minute=minute, second=0, microsecond=0)


MON, TUE, WED, THU, FRI, SAT, SUN = range(7)


def seed():
    db = SessionLocal()
    now = datetime.now()

    created_rides = []
    created_requests = []
    created_tokens = []

    def add_past_ride(driver_id, from_pt, to_pt, dep_time, passenger_id, pickup_pt=None):
        """Creates one completed Ride + one dropped RideRequest for a passenger."""
        seats = 1 if driver_id in BIKE_DRIVERS else 3
        ride = Ride(
            driver_id=driver_id,
            vehicle_id=VEHICLE_OF[driver_id],
            from_address="Test pickup",
            from_lat=from_pt[0], from_lng=from_pt[1],
            to_address="Test dropoff",
            to_lat=to_pt[0], to_lng=to_pt[1],
            departure_time=dep_time,
            seats_available=seats,
            ac=True if driver_id not in BIKE_DRIVERS else None,
            gender_filter="any",
            fare_per_seat=250.0,
            status="completed",
        )
        db.add(ride)
        db.flush()  # get ride.id

        pu = pickup_pt or from_pt
        req = RideRequest(
            ride_id=ride.id,
            passenger_id=passenger_id,
            status="dropped",
            pickup_lat=pu[0],
            pickup_lng=pu[1],
        )
        db.add(req)
        created_rides.append(ride)
        created_requests.append(req)
        return ride, req

    def add_future_ride(driver_id, from_pt, to_pt, dep_time, seats=None, note=""):
        """Creates one active future Ride (a driver's posted offer)."""
        seats = seats if seats is not None else (1 if driver_id in BIKE_DRIVERS else 3)
        ride = Ride(
            driver_id=driver_id,
            vehicle_id=VEHICLE_OF[driver_id],
            from_address=f"Test pickup ({note})" if note else "Test pickup",
            from_lat=from_pt[0], from_lng=from_pt[1],
            to_address=f"Test dropoff ({note})" if note else "Test dropoff",
            to_lat=to_pt[0], to_lng=to_pt[1],
            departure_time=dep_time,
            seats_available=seats,
            ac=True if driver_id not in BIKE_DRIVERS else None,
            gender_filter="any",
            fare_per_seat=250.0,
            status="active",
        )
        db.add(ride)
        created_rides.append(ride)
        return ride

    # ════════════════════════════════════════════════════════════
    # 1) BUFFER RIDE — satisfies the 7-day recency gate for everyone
    # ════════════════════════════════════════════════════════════
    buffer_dep = at(now - timedelta(days=2), 8, 0)
    buffer_ride = Ride(
        driver_id=JUNAID_ID,
        vehicle_id=VEHICLE_OF[JUNAID_ID],
        from_address="Gulshan-e-Iqbal (buffer)",
        from_lat=GULSHAN[0], from_lng=GULSHAN[1],
        to_address="DSU (buffer)",
        to_lat=DSU[0], to_lng=DSU[1],
        departure_time=buffer_dep,
        seats_available=6,
        ac=True,
        gender_filter="any",
        fare_per_seat=250.0,
        status="completed",
    )
    db.add(buffer_ride)
    db.flush()
    for pid in [BUSHRA_ID, ZEESHAN_ID, AQSA_ID, ARNAV_ID, ASAD_ID, POOJA_ID, MINAL_ID]:
        req = RideRequest(
            ride_id=buffer_ride.id,
            passenger_id=pid,
            status="dropped",
            pickup_lat=GULSHAN[0],
            pickup_lng=GULSHAN[1],
        )
        db.add(req)
        created_requests.append(req)
    created_rides.append(buffer_ride)

    # ════════════════════════════════════════════════════════════
    # 2) BUSHRA (1) — multi-weekday pattern: Mon + Wed, Gulshan -> DSU ~08:00
    # ════════════════════════════════════════════════════════════
    add_past_ride(JUNAID_ID, GULSHAN, DSU, at(most_recent_weekday(now, MON, 1), 8, 0), BUSHRA_ID)
    add_past_ride(JUNAID_ID, GULSHAN, DSU, at(most_recent_weekday(now, MON, 0), 8, 5), BUSHRA_ID)
    add_past_ride(ZAINAB_ID, GULSHAN, DSU, at(most_recent_weekday(now, WED, 1), 8, 10), BUSHRA_ID)
    add_past_ride(ZAINAB_ID, GULSHAN, DSU, at(most_recent_weekday(now, WED, 0), 7, 55), BUSHRA_ID)

    # ════════════════════════════════════════════════════════════
    # 3) ZEESHAN (2) — exactly ONE ride ever -> threshold test (should be skipped)
    # ════════════════════════════════════════════════════════════
    add_past_ride(JUNAID_ID, GULSHAN, DSU, at(most_recent_weekday(now, TUE, 0), 8, 0), ZEESHAN_ID)

    # ════════════════════════════════════════════════════════════
    # 4) AQSA (4) — random/inconsistent weekdays -> no pattern should form
    # ════════════════════════════════════════════════════════════
    add_past_ride(HAROON_ID, SADDAR, DSU, at(most_recent_weekday(now, TUE, 2), 9, 0), AQSA_ID)
    add_past_ride(MAHESH_ID, FB_AREA, DSU, at(most_recent_weekday(now, THU, 1), 10, 0), AQSA_ID)
    add_past_ride(ZAINAB_ID, JOHAR_16, DSU, at(most_recent_weekday(now, FRI, 0), 7, 45), AQSA_ID)

    # ════════════════════════════════════════════════════════════
    # 5) ARNAV (5) — Saddar -> DSU, Monday ~08:00 pattern (time-margin fail test)
    # ════════════════════════════════════════════════════════════
    add_past_ride(HAROON_ID, SADDAR, DSU, at(most_recent_weekday(now, MON, 1), 8, 0), ARNAV_ID)
    add_past_ride(HAROON_ID, SADDAR, DSU, at(most_recent_weekday(now, MON, 0), 8, 5), ARNAV_ID)

    # ════════════════════════════════════════════════════════════
    # 6) ASAD ALI (6) — DSU -> Clifton, Wednesday ~15:00 pattern (positive, evening)
    # ════════════════════════════════════════════════════════════
    add_past_ride(ALI_ID, DSU, CLIFTON, at(most_recent_weekday(now, WED, 1), 15, 0), ASAD_ID)
    add_past_ride(ALI_ID, DSU, CLIFTON, at(most_recent_weekday(now, WED, 0), 15, 10), ASAD_ID)

    # ════════════════════════════════════════════════════════════
    # 7) POOJA (7) — FB Area -> DSU, Tuesday ~09:30 pattern (established,
    #    but NO future driver ride will be posted near it -> negative case)
    # ════════════════════════════════════════════════════════════
    add_past_ride(MAHESH_ID, FB_AREA, DSU, at(most_recent_weekday(now, TUE, 2), 9, 30), POOJA_ID)
    add_past_ride(MAHESH_ID, FB_AREA, DSU, at(most_recent_weekday(now, TUE, 1), 9, 25), POOJA_ID)

    # ════════════════════════════════════════════════════════════
    # 8) MINAL (3, passenger+driver) — Garden East -> DSU, Friday ~08:00
    #    Her OWN future ride will match this exactly -> self-exclusion check
    # ════════════════════════════════════════════════════════════
    add_past_ride(JUNAID_ID, GARDEN_E, DSU, at(most_recent_weekday(now, FRI, 2), 8, 0), MINAL_ID)
    add_past_ride(JUNAID_ID, GARDEN_E, DSU, at(most_recent_weekday(now, FRI, 1), 8, 5), MINAL_ID)

    db.flush()

    # ════════════════════════════════════════════════════════════
    # FUTURE (active) rides — what the matching engine should find
    # ════════════════════════════════════════════════════════════

    # A) Junaid: Mon (+1wk) 08:00, Gulshan -> DSU
    #    -> should match Bushra's Monday pattern EXACTLY
    add_future_ride(JUNAID_ID, GULSHAN, DSU, at(next_weekday(now, MON, 0), 8, 0), seats=3,
                     note="matches Bushra Monday")

    # B) Zainab: Wed (+1wk) 08:00, Johar Block 16 -> DSU
    #    -> Johar is 2.9km from Gulshan, well within current 15km radius
    #    -> should match Bushra's Wednesday pattern (near-miss location test)
    add_future_ride(ZAINAB_ID, JOHAR_16, DSU, at(next_weekday(now, WED, 0), 8, 0), seats=2,
                     note="matches Bushra Wednesday via nearby pickup")

    # C) Haroon: Mon (+1wk) 09:15, Saddar -> DSU
    #    -> Arnav's pattern is ~08:00; this is 75 min off (current margin is 30 min)
    #    -> should NOT match Arnav (time-margin negative test)
    add_future_ride(HAROON_ID, SADDAR, DSU, at(next_weekday(now, MON, 0), 9, 15), seats=1,
                     note="time-mismatch for Arnav")

    # D) Ali Farooq: Wed (+1wk) 15:00, DSU -> Clifton
    #    -> should match Asad's Wednesday evening pattern EXACTLY
    add_future_ride(ALI_ID, DSU, CLIFTON, at(next_weekday(now, WED, 0), 15, 0), seats=1,
                     note="matches Asad Wednesday evening")

    # E) (Deliberately no future Tuesday / FB Area ride posted at all)
    #    -> Pooja has an established pattern but nothing to match ->
    #       negative test: "pattern exists, no active offer available"

    # F) Minal (driver) posts her OWN Friday pattern back to herself
    #    -> Ride.driver_id != passenger_id filter should exclude this from
    #       Minal's own recommendations even though it matches perfectly
    add_future_ride(MINAL_ID, GARDEN_E, DSU, at(next_weekday(now, FRI, 0), 8, 0), seats=3,
                     note="Minal's own ride - should NOT self-recommend")

    db.flush()

    # ════════════════════════════════════════════════════════════
    # DEVICE TOKENS — required, or these passengers are skipped entirely
    # ════════════════════════════════════════════════════════════
    for pid in [BUSHRA_ID, ZEESHAN_ID, AQSA_ID, ARNAV_ID, ASAD_ID, POOJA_ID, MINAL_ID]:
        # Skip if a token already exists for this user (avoid duplicates on re-run)
        existing = db.query(DeviceToken).filter(DeviceToken.user_id == pid).first()
        if existing:
            continue
        token = DeviceToken(
            user_id=pid,
            token=f"TEST_FAKE_FCM_TOKEN_USER_{pid}_{'x' * 100}",
        )
        db.add(token)
        created_tokens.append(token)

    db.commit()

    print(f"Seed complete:")
    print(f"  Rides created:        {len(created_rides)}")
    print(f"  Ride requests created:{len(created_requests)}")
    print(f"  Device tokens created:{len(created_tokens)}")
    print()
    print("Now call POST /recommendations/test-run to check the results.")

    db.close()


if __name__ == "__main__":
    seed()
