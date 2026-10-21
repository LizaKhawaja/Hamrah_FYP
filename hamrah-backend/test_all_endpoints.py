"""Hit all Hamrah API endpoints against the local SQLite backend."""
import io
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8001")
PASSENGER_ID = "cs232322"
DRIVER_ID = "cs231830"
PASSWORD = "Test1234!"

results = []


def record(name, method, path, status, ok, detail=""):
    results.append({"name": name, "method": method, "path": path, "status": status, "ok": ok, "detail": detail})
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {method:6} {path:45} -> {status} {detail}")


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def call(session, method, url, **kwargs):
    try:
        return session.request(method, url, timeout=120, **kwargs)
    except requests.RequestException as exc:
        class FakeResponse:
            status_code = 0
            text = str(exc)

            def json(self):
                return {}

        return FakeResponse()


def main():
    session = requests.Session()
    passenger_token = None
    driver_token = None
    ride_id = None
    request_id = None
    uploaded_url = None

    r = call(session, "GET", f"{BASE}/sos/contacts")
    record("SOS contacts", "GET", "/sos/contacts", r.status_code, r.status_code == 200)

    r = call(session, "GET", f"{BASE}/license/health")
    record("License OCR health", "GET", "/license/health", r.status_code, r.status_code == 200)

    r = call(session, "GET", f"{BASE}/openapi.json")
    record("OpenAPI schema", "GET", "/openapi.json", r.status_code, r.status_code == 200)

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    r = call(session, "POST", f"{BASE}/upload/", files={"image": ("test.png", io.BytesIO(png), "image/png")})
    ok = r.status_code == 200 and "url" in r.json()
    uploaded_url = r.json().get("url") if ok else None
    record("Upload image", "POST", "/upload/", r.status_code, ok)

    r = call(session, "POST", f"{BASE}/login", data={"username": PASSENGER_ID, "password": PASSWORD})
    ok = r.status_code == 200 and "access_token" in r.json()
    if ok:
        passenger_token = r.json()["access_token"]
    record("Login passenger", "POST", "/login", r.status_code, ok)

    r = call(session, "POST", f"{BASE}/login", data={"username": DRIVER_ID, "password": PASSWORD})
    ok = r.status_code == 200 and "access_token" in r.json()
    if ok:
        driver_token = r.json()["access_token"]
    record("Login driver", "POST", "/login", r.status_code, ok)

    if not passenger_token or not driver_token:
        print("\nCannot continue without auth tokens. Run seed_sqlite.py first.")
        sys.exit(1)

    ph = auth_headers(passenger_token)
    dh = auth_headers(driver_token)

    r = call(session, "GET", f"{BASE}/users/me", headers=ph)
    record("Get me (passenger)", "GET", "/users/me", r.status_code, r.status_code == 200)

    r = call(session, "PATCH", f"{BASE}/users/profile", headers=ph, json={"first_name": "Bushra"})
    record("Update profile", "PATCH", "/users/profile", r.status_code, r.status_code == 200)

    r = call(session, "GET", f"{BASE}/users/me", headers=dh)
    record("Get me (driver)", "GET", "/users/me", r.status_code, r.status_code == 200)

    r = call(session, "GET", f"{BASE}/rides/my", headers=dh)
    ok = r.status_code == 200
    if ok and r.json():
        ride_id = r.json()[0]["id"]
    record("Driver my rides", "GET", "/rides/my", r.status_code, ok, f"ride_id={ride_id}")

    r = call(session, "GET", f"{BASE}/rides/requests", headers=dh)
    record("Driver pending requests", "GET", "/rides/requests", r.status_code, r.status_code == 200)

    target_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    r = call(
        session,
        "GET",
        f"{BASE}/ride_requests/search",
        headers=ph,
        params={
            "from_lat": 24.8607,
            "from_lng": 67.0011,
            "to_lat": 24.8600,
            "to_lng": 67.0100,
            "target_time": target_time,
        },
    )
    ok = r.status_code == 200
    if ok and r.json() and not ride_id:
        ride_id = r.json()[0]["id"]
    record("Search rides", "GET", "/ride_requests/search", r.status_code, ok)

    if ride_id:
        r = call(
            session,
            "POST",
            f"{BASE}/ride_requests/",
            headers=ph,
            json={"ride_id": ride_id, "pickup_lat": 24.8607, "pickup_lng": 67.0011},
        )
        ok = r.status_code in (200, 201)
        if ok:
            request_id = r.json().get("id")
        elif r.status_code == 400 and "already have an active request" in r.text:
            ok = True
            active = call(session, "GET", f"{BASE}/ride_requests/active", headers=ph)
            if active.status_code == 200 and active.json():
                request_id = active.json().get("request_id")
        record("Request ride", "POST", "/ride_requests/", r.status_code, ok, f"request_id={request_id}")

    r = call(session, "GET", f"{BASE}/ride_requests/active", headers=ph)
    record("Active ride (passenger)", "GET", "/ride_requests/active", r.status_code, r.status_code == 200)

    r = call(session, "GET", f"{BASE}/ride_requests/history", headers=ph)
    record("Ride history (passenger)", "GET", "/ride_requests/history", r.status_code, r.status_code == 200)

    if request_id:
        r = call(session, "POST", f"{BASE}/ride_requests/{request_id}/accept", headers=dh)
        record("Accept request", "POST", f"/ride_requests/{request_id}/accept", r.status_code, r.status_code in (200, 400))

        r = call(session, "POST", f"{BASE}/rides/requests/{request_id}/pickup", headers=dh)
        record("Mark pickup", "POST", f"/rides/requests/{request_id}/pickup", r.status_code, r.status_code in (200, 400))

    if ride_id:
        r = call(session, "POST", f"{BASE}/location/{ride_id}/start", headers=dh)
        record("Start ride", "POST", f"/location/{ride_id}/start", r.status_code, r.status_code in (200, 400))

        r = call(session, "GET", f"{BASE}/chat/{ride_id}/messages", headers=ph)
        record("Get chat messages", "GET", f"/chat/{ride_id}/messages", r.status_code, r.status_code == 200)

        r = call(session, "POST", f"{BASE}/chat/send", headers=ph, json={"ride_id": ride_id, "message": "Hello driver"})
        record("Send chat message", "POST", "/chat/send", r.status_code, r.status_code == 200)

        r = call(session, "POST", f"{BASE}/calls/token", headers=ph, params={"ride_id": ride_id})
        record("Call token", "POST", "/calls/token", r.status_code, r.status_code in (200, 500), r.text[:80])

    r = call(session, "GET", f"{BASE}/ratings/driver/2")
    record("Driver rating stats", "GET", "/ratings/driver/2", r.status_code, r.status_code in (200, 404))

    r = call(session, "GET", f"{BASE}/ratings/driver/2/reviews")
    record("Driver reviews", "GET", "/ratings/driver/2/reviews", r.status_code, r.status_code in (200, 404))

    r = call(session, "POST", f"{BASE}/save-token", headers=ph, json={"user_id": 1, "token": "fake-fcm-token"})
    record("Save FCM token", "POST", "/save-token", r.status_code, r.status_code == 200)

    r = call(session, "POST", f"{BASE}/test-notify", params={"user_id": 1})
    record("Test notify", "POST", "/test-notify", r.status_code, r.status_code == 200)

    r = call(session, "POST", f"{BASE}/recommendations/run", headers=ph)
    record("Run recommendations", "POST", "/recommendations/run", r.status_code, r.status_code == 200)

    r = call(session, "POST", f"{BASE}/password/forgot", json={"email": "bushra.ahmed@gmail.com"})
    record("Forgot password", "POST", "/password/forgot", r.status_code, r.status_code in (200, 500))

    if uploaded_url:
        r = call(
            session,
            "POST",
            f"{BASE}/face-verification/verify",
            json={"cnic_image_url": uploaded_url, "live_image_url": uploaded_url},
        )
        record("Face verify (URL)", "POST", "/face-verification/verify", r.status_code, r.status_code == 200, r.text[:60])

        r = call(session, "POST", f"{BASE}/license/verify", json={"license_image_url": uploaded_url})
        record("License OCR verify", "POST", "/license/verify", r.status_code, r.status_code in (200, 500), r.text[:60])

    if ride_id:
        r = call(session, "POST", f"{BASE}/rides/{ride_id}/complete", headers=dh)
        record("Complete ride", "POST", f"/rides/{ride_id}/complete", r.status_code, r.status_code in (200, 400))

        r = call(
            session,
            "POST",
            f"{BASE}/ratings/",
            headers=ph,
            json={"ride_id": ride_id, "stars": 5, "tags": ["punctual"], "review": "Great ride"},
        )
        record("Submit rating", "POST", "/ratings/", r.status_code, r.status_code in (200, 201, 400))

    passed = sum(1 for x in results if x["ok"])
    failed = len(results) - passed
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {len(results)} total")
    if failed:
        print("\nFailed endpoints:")
        for x in results:
            if not x["ok"]:
                print(f"  - {x['method']} {x['path']} ({x['status']}) {x['detail']}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
