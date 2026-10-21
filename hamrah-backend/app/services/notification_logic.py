from app.services.fcm_service import send_notification
from app.models import User, DeviceToken, Notification


def _get_tokens(db, user_id):
    tokens = db.query(DeviceToken).filter(DeviceToken.user_id == user_id).all()
    return [t.token for t in tokens]


def _get_name(db, user_id):
    user = db.query(User).filter(User.id == user_id).first()
    return f"{user.first_name} {user.last_name}" if user else "Someone"


def save_notification(db, user_id, title, body, notif_type, data=None):
    n = Notification(
        user_id=user_id,
        type=notif_type,
        title=title,
        body=body,
        data=data,
    )
    db.add(n)
    db.commit()
    return n


def notify_driver_new_request(db, driver_id, passenger_id):
    tokens = _get_tokens(db, driver_id)
    name = _get_name(db, passenger_id)
    title = "New Ride Request"
    body = f"{name} has requested a seat in your ride"
    send_notification(tokens, title=title, body=body, data={"type": "new_ride_request"})
    save_notification(db, driver_id, title, body, "new_ride_request", data={"passenger_id": passenger_id})


def notify_passenger_request_accepted(db, passenger_id, driver_id):
    tokens = _get_tokens(db, passenger_id)
    name = _get_name(db, driver_id)
    title = "Request Accepted "
    body = f"{name} accepted your ride request. Get ready!"
    send_notification(tokens, title=title, body=body)
    save_notification(db, passenger_id, title, body, "request_accepted", data={"driver_id": driver_id})


def notify_passenger_request_rejected(db, passenger_id, driver_id):
    tokens = _get_tokens(db, passenger_id)
    name = _get_name(db, driver_id)
    title = "Request Rejected "
    body = f"{name} could not accommodate your request. Try another ride."
    send_notification(tokens, title=title, body=body)
    save_notification(db, passenger_id, title, body, "request_rejected", data={"driver_id": driver_id})


def notify_driver_request_cancelled(db, driver_id, passenger_id):
    tokens = _get_tokens(db, driver_id)
    name = _get_name(db, passenger_id)
    title = "Request Cancelled"
    body = f"{name} cancelled their ride request"
    send_notification(tokens, title=title, body=body)
    save_notification(db, driver_id, title, body, "request_cancelled", data={"passenger_id": passenger_id})

def notify_passengers_ride_started(db, passenger_ids, driver_id):
    driver_name = _get_name(db, driver_id)
    title = "Ride Started "
    body = f"{driver_name} has started the ride. Please be at your pickup point!"
    for pid in passenger_ids:
        tokens = _get_tokens(db, pid)
        send_notification(tokens, title=title, body=body)
        save_notification(db, pid, title, body, "ride_started", data={"driver_id": driver_id})


def notify_passenger_picked_up(db, passenger_id, driver_id):
    tokens = _get_tokens(db, passenger_id)
    driver_name = _get_name(db, driver_id)
    title = "You're On Board! "
    body = f"{driver_name} has marked you as picked up. Enjoy the ride!"
    send_notification(tokens, title=title, body=body)
    save_notification(db, passenger_id, title, body, "picked_up", data={"driver_id": driver_id})


def notify_passengers_ride_completed(db, passenger_ids, driver_id):
    driver_name = _get_name(db, driver_id)
    title = "Ride Completed "
    body = f"Your ride with {driver_name} is complete. Hope you had a great trip!"
    for pid in passenger_ids:
        tokens = _get_tokens(db, pid)
        send_notification(tokens, title=title, body=body)
        save_notification(db, pid, title, body, "ride_completed", data={"driver_id": driver_id})


def notify_passengers_ride_cancelled(db, passenger_ids, driver_id):
    driver_name = _get_name(db, driver_id)
    title = "Ride Cancelled "
    body = f"{driver_name} has cancelled the ride. Please look for another ride."
    for pid in passenger_ids:
        tokens = _get_tokens(db, pid)
        send_notification(tokens, title=title, body=body)
        save_notification(db, pid, title, body, "ride_cancelled", data={"driver_id": driver_id})


def notify_passenger_arrived(db, passenger_id, driver_id):
    tokens = _get_tokens(db, passenger_id)
    driver_name = _get_name(db, driver_id)
    title = "Driver Arrived 📍"
    body = f"{driver_name} has arrived at your pickup location!"
    send_notification(tokens, title=title, body=body)
    save_notification(db, passenger_id, title, body, "driver_arrived", data={"driver_id": driver_id})