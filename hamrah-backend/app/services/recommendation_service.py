import json
import logging
import math
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import RideRequest, Ride, User, DeviceToken
from app.services.fcm_service import send_notification

logger = logging.getLogger(__name__)

WEEKDAY_NAMES = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday",
]

MIN_RIDES_FOR_PATTERN = 2
COMPLETED_REQUEST_STATUSES = ["dropped", "rated"]


def haversine(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(d_lng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_ride_history_summary(db: Session, passenger_id: int, days: int = 7) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None)
    requests = (
        db.query(RideRequest)
        .join(Ride, Ride.id == RideRequest.ride_id)
        .filter(
            RideRequest.passenger_id == passenger_id,
            RideRequest.status.in_(COMPLETED_REQUEST_STATUSES),
            Ride.departure_time >= since,
        )
        .all()
    )
    summary = []
    for req in requests:
        ride = req.ride
        dep = ride.departure_time
        dep_local = dep.replace(tzinfo=None) if dep.tzinfo is None else dep.replace(tzinfo=None)
        summary.append({
            "weekday":       dep_local.weekday(),
            "weekday_name":  WEEKDAY_NAMES[dep_local.weekday()],
            "hour":          dep_local.hour,
            "minute":        dep_local.minute,
            "from_address":  ride.from_address,
            "to_address":    ride.to_address,
            "from_lat":      ride.from_lat,
            "from_lng":      ride.from_lng,
            "to_lat":        ride.to_lat,
            "to_lng":        ride.to_lng,
            "fare":          ride.fare_per_seat,
        })
    return summary


def call_llm(history: list[dict]) -> dict | None:
    if not settings.ai_api_key or not settings.ai_enabled:
        return None
    if len(history) < MIN_RIDES_FOR_PATTERN:
        logger.info(f"[AI] Only {len(history)} ride(s) in history, skipping AI and using rule-based fallback")
        return None

    system_prompt = (
        "You are a smart commute-pattern analyser for a university carpool app. "
        "Given a passenger's recent ride history, identify the route + day + time "
        "they are MOST LIKELY to want next. "
        "ONLY OUTPUT A JSON OBJECT, NO OTHER TEXT AT ALL, NO EXPLANATIONS, NO CODE, NO MARKDOWN."
    )
    user_prompt = f"""Passenger ride history (last 7 days):
{json.dumps(history, indent=2, default=str)}

Return a JSON object with these exact keys:
- "weekday": integer 0-6 (0=Monday ... 6=Sunday)
- "hour": integer 0-23
- "minute": integer 0-59
- "from_address": string
- "to_address": string
- "from_lat": float
- "from_lng": float
- "to_lat": float
- "to_lng": float
- "reason": short string explaining the pattern (1 sentence)

If the history is empty or too sparse, return JSON: {{"weekday": null}}."""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            if settings.ai_provider == "gemini":
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{settings.ai_model}:generateContent?key={settings.ai_api_key}"
                )
                payload = {
                    "contents": [{
                        "parts": [{"text": system_prompt + "\n\n" + user_prompt}]
                    }],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400},
                }
                r = httpx.post(url, json=payload, timeout=30.0)
                r.raise_for_status()
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            else:
                base = "https://api.openai.com/v1/chat/completions"
                if settings.ai_provider == "groq":
                    base = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {settings.ai_api_key}",
                    "Content-Type":  "application/json",
                }
                payload = {
                    "model":       settings.ai_model,
                    "messages":    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens":  1000,
                }
                r = httpx.post(base, headers=headers, json=payload, timeout=30.0)
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"]

            match = re.search(r"```json\s*(\{.*?\})\s*```|\{.*?\}", text, re.DOTALL)
            if match:
                json_str = match.group(1) if match.group(1) else match.group(0)
                try:
                    return json.loads(json_str)
                except Exception as e:
                    logger.warning(f"[AI] Failed to parse JSON: {e}, JSON string: {json_str}")
                    return None
            logger.warning(f"[AI] No JSON found in LLM response: {text[:200]}")
            return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait_time = (2 ** attempt) + 1
                if attempt < max_retries - 1:
                    logger.warning(f"[AI] Rate limited, retrying in {wait_time}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.warning(f"[AI] Max retries reached after 429 errors, using rule-based fallback")
                    return None
            else:
                logger.error(f"[AI] LLM call failed with status {e.response.status_code}: {e}")
                return None
        except Exception as e:
            logger.error(f"[AI] LLM call failed: {e}")
            return None
    return None


def get_passenger_patterns(db: Session, passenger_id: int) -> list[dict]:
    
    since = (datetime.now(timezone.utc) - timedelta(days=30)).replace(tzinfo=None)

    requests = (
        db.query(RideRequest)
        .join(Ride, Ride.id == RideRequest.ride_id)
        .filter(
            RideRequest.passenger_id == passenger_id,
            RideRequest.status.in_(COMPLETED_REQUEST_STATUSES),
            Ride.departure_time >= since,
        )
        .all()
    )

    if not requests:
        return []

    entries = []
    for req in requests:
        ride = req.ride
        dep = ride.departure_time
        if dep.tzinfo is None:
            dep = dep.replace(tzinfo=timezone.utc)

        entries.append({
            "weekday":   dep.weekday(),
            "hour":      dep.hour,
            "from_lat":  req.pickup_lat or ride.from_lat,
            "from_lng":  req.pickup_lng or ride.from_lng,
            "to_lat":    ride.to_lat,
            "to_lng":    ride.to_lng,
            "gender_filter": ride.gender_filter,
        })

    if not entries:
        return []

    by_weekday: dict[int, list[dict]] = defaultdict(list)
    for e in entries:
        by_weekday[e["weekday"]].append(e)

    passenger = db.query(User).filter(User.id == passenger_id).first()
    gender = passenger.gender if passenger else "any"

    patterns = []
    for weekday, day_entries in by_weekday.items():
        if len(day_entries) < MIN_RIDES_FOR_PATTERN:
            logger.info(
                f"[Recommendations] passenger {passenger_id} has only "
                f"{len(day_entries)} ride(s) on {WEEKDAY_NAMES[weekday]} "
                f"(needs {MIN_RIDES_FOR_PATTERN}) — skipping this weekday"
            )
            continue

        hour = Counter(e["hour"] for e in day_entries).most_common(1)[0][0]
        avg_pickup_lat = sum(e["from_lat"] for e in day_entries) / len(day_entries)
        avg_pickup_lng = sum(e["from_lng"] for e in day_entries) / len(day_entries)
        avg_to_lat = sum(e["to_lat"] for e in day_entries) / len(day_entries)
        avg_to_lng = sum(e["to_lng"] for e in day_entries) / len(day_entries)

        patterns.append({
            "passenger_id":   passenger_id,
            "weekday":        weekday,
            "hour":           hour,
            "minute":         0,
            "from_lat":       avg_pickup_lat,
            "from_lng":       avg_pickup_lng,
            "to_lat":         avg_to_lat,
            "to_lng":         avg_to_lng,
            "from_address":   "",
            "to_address":     "",
            "gender":         gender,
            "ride_count":     len(day_entries),
            "reason":         f"You usually ride on {WEEKDAY_NAMES[weekday]}s around this time",
        })

    logger.info(
        f"[Recommendations] passenger {passenger_id} has {len(patterns)} "
        f"recurring weekday pattern(s): {[WEEKDAY_NAMES[p['weekday']] for p in patterns]}"
    )
    return patterns

#conver lon and lat in readable address
def _resolve_address(db: Session, lat: float, lng: float) -> str:
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"format": "json", "lat": lat, "lon": lng, "zoom": 16, "addressdetails": 0}
        headers = {"User-Agent": "HamrahCarpoolApp/1.0"}
        r = httpx.get(url, params=params, headers=headers, timeout=8.0)
        if r.status_code == 200:
            return r.json().get("display_name", f"{lat:.4f}, {lng:.4f}")
    except Exception as e:
        logger.warning(f"[AI] Reverse geocode failed: {e}")
    return f"{lat:.4f}, {lng:.4f}"


def find_matching_rides(db: Session, pattern: dict, passenger_id: int) -> list:
    target_weekday = pattern.get("weekday")
    target_hour    = pattern.get("hour", 0)
    target_minute  = pattern.get("minute", 0)

    if target_weekday is None:
        return []

    now = datetime.now(timezone.utc)
    matched = []

    logger.info(
        f"[Recommendations] looking for rides for pattern: "
        f"weekday={WEEKDAY_NAMES[target_weekday]}, "
        f"time={target_hour:02d}:{target_minute:02d}, "
        f"from lat/lng={pattern.get('from_lat'):.4f}/{pattern.get('from_lng'):.4f}, "
        f"to lat/lng={pattern.get('to_lat'):.4f}/{pattern.get('to_lng'):.4f}"
    )

    all_active_rides = (
        db.query(Ride)
        .filter(
            Ride.status == "active",
            Ride.departure_time >= now.replace(tzinfo=None),
            Ride.seats_available > 0,
            Ride.driver_id != passenger_id,
        )
        .all()
    )

    already_requested = {
        rr.ride_id
        for rr in db.query(RideRequest).filter(
            RideRequest.passenger_id == passenger_id,
            RideRequest.status.in_(["pending", "accepted"] + COMPLETED_REQUEST_STATUSES),
        ).all()
    }

    for ride in all_active_rides:
        if ride.id in already_requested:
            continue
        ride_dep = ride.departure_time

        if ride_dep.tzinfo is None:
            ride_dep = ride_dep.replace(tzinfo=timezone.utc)

        ride_weekday = ride_dep.weekday()
        ride_hour = ride_dep.hour
        ride_minute = ride_dep.minute

        if ride_weekday != target_weekday:
            continue

        predicted_minutes = target_hour * 60 + target_minute
        ride_minutes = ride_hour * 60 + ride_minute
        time_difference = abs(predicted_minutes - ride_minutes)

        if time_difference > 30:
            continue

        pickup_dist = haversine(
            pattern.get("from_lat") or ride.from_lat,
            pattern.get("from_lng") or ride.from_lng,
            ride.from_lat, ride.from_lng,
        )
        dropoff_dist = haversine(
            pattern.get("to_lat") or ride.to_lat,
            pattern.get("to_lng") or ride.to_lng,
            ride.to_lat, ride.to_lng,
        )

        logger.info(
            f"[Recommendations] checking ride {ride.id}: "
            f"pickup_dist={pickup_dist:.1f}km, dropoff_dist={dropoff_dist:.1f}km"
        )

        if pickup_dist <= 15 and dropoff_dist <= 15:
            matched.append(ride)

    logger.info(f"[Recommendations] found {len(matched)} matching rides")
    return matched

def send_recommendation_notification(
    db: Session, passenger_id: int, rides: list, reason: str
):
    tokens = [
        t.token for t in
        db.query(DeviceToken).filter(DeviceToken.user_id == passenger_id).all()
    ]
    if not rides:
        return

    best = sorted(rides, key=lambda r: (r.departure_time, -r.seats_available))[0]

    driver = db.query(User).filter(User.id == best.driver_id).first()
    driver_name = f"{driver.first_name} {driver.last_name}" if driver else "A driver"
    dep = best.departure_time
    if dep.tzinfo is None:
        dep = dep.replace(tzinfo=timezone.utc)
    time_str = dep.strftime("%I:%M %p")

    vehicle_number = ""
    if best.vehicle_id:
        from app.models import Vehicle
        vehicle = db.query(Vehicle).filter(Vehicle.id == best.vehicle_id).first()
        if vehicle:
            vehicle_number = vehicle.vehicle_number or ""

    title = "🚗 Ride Pick For You"
    body = (
        f"{driver_name} is leaving near your usual route at {time_str} on "
        f"{WEEKDAY_NAMES[dep.weekday()]}. Tap to book!"
    )

    payload = {
        "type":            "ride_recommendation",
        "ride_id":         str(best.id) if best.id else "",
        "driver_id":       str(best.driver_id) if best.driver_id else "",
        "driver_name":     driver_name,
        "from_address":    best.from_address or "",
        "to_address":      best.to_address or "",
        "from_lat":        str(best.from_lat) if best.from_lat else "",
        "from_lng":        str(best.from_lng) if best.from_lng else "",
        "to_lat":          str(best.to_lat) if best.to_lat else "",
        "to_lng":          str(best.to_lng) if best.to_lng else "",
        "departure_time":  dep.isoformat(),
        "fare":            str(best.fare_per_seat or 0),
        "seats_available": str(best.seats_available or 0),
        "vehicle_number":  vehicle_number,
        "reason":          reason,
    }

    if tokens:
        send_notification(tokens, title=title, body=body, data=payload)

    from app.services.notification_logic import save_notification
    save_notification(
        db, passenger_id, title, body,
        notif_type="ride_recommendation",
        data=payload,
    )

def run_recommendations(db: Session) -> list:
    passengers_with_tokens = (
        db.query(User)
        .join(DeviceToken, User.id == DeviceToken.user_id)
        .filter(User.is_passenger == True)
        .distinct()
        .all()
    )
    results = []
    ai_used = bool(settings.ai_enabled and settings.ai_api_key)
    logger.info(
        f"[Recommendations] starting — AI={'on' if ai_used else 'off'}, "
        f"provider={settings.ai_provider}, model={settings.ai_model}, "
        f"passengers with tokens: {len(passengers_with_tokens)}"
    )

    for passenger in passengers_with_tokens:
        try:
            history = get_ride_history_summary(db, passenger.id)
            if not history:
                logger.info(f"[Recommendations] skipping passenger {passenger.id} — no ride history")
                continue

            used_ai = False
            patterns = get_passenger_patterns(db, passenger.id)

            if ai_used:
                ai_pattern = call_llm(history)
                if ai_pattern and ai_pattern.get("weekday") is not None:
                    patterns = [ai_pattern]
                    used_ai = True
                time.sleep(1.0)

            if not patterns:
                logger.info(f"[Recommendations] skipping passenger {passenger.id} — no established pattern")
                continue

            all_matched = {}
            matched_pattern_summaries = []

            for pattern in patterns:
                if pattern.get("from_lat") and not pattern.get("from_address"):
                    pattern["from_address"] = _resolve_address(db, pattern["from_lat"], pattern["from_lng"])
                if pattern.get("to_lat") and not pattern.get("to_address"):
                    pattern["to_address"] = _resolve_address(db, pattern["to_lat"], pattern["to_lng"])

                matched = find_matching_rides(db, pattern, passenger.id)
                if not matched:
                    continue

                for r in matched:
                    all_matched[r.id] = r

                matched_pattern_summaries.append({
                    "weekday":  WEEKDAY_NAMES[pattern["weekday"]],
                    "hour":     pattern["hour"],
                    "minute":   pattern.get("minute", 0),
                    "from":     pattern.get("from_address", ""),
                    "to":       pattern.get("to_address", ""),
                    "reason":   pattern.get("reason", ""),
                })

            if not all_matched:
                logger.info(f"[Recommendations] skipping passenger {passenger.id} — no matching rides for any pattern")
                continue

            matched_rides = list(all_matched.values())
            top_reason = matched_pattern_summaries[0]["reason"] if matched_pattern_summaries else "Based on your ride history"

            send_recommendation_notification(db, passenger.id, matched_rides, top_reason)

            results.append({
                "passenger_id":   passenger.id,
                "passenger_name": f"{passenger.first_name} {passenger.last_name}",
                "used_ai":        used_ai,
                "patterns":       matched_pattern_summaries,
                "recommended_rides": [
                    {
                        "ride_id":    r.id,
                        "driver_id":  r.driver_id,
                        "from":       r.from_address,
                        "to":         r.to_address,
                        "departure":  r.departure_time.isoformat(),
                        "fare":       r.fare_per_seat,
                        "seats_left": r.seats_available,
                    }
                    for r in matched_rides
                ],
            })
        except Exception as e:
            logger.error(f"[Recommendations] error for passenger {passenger.id}: {e}")

    logger.info(f"[Recommendations] done — {len(results)} passenger(s) notified")
    return results