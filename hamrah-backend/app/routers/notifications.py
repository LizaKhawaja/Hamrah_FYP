from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DeviceToken, Notification
from app.schemas import TokenRequest
from app.services.fcm_service import send_notification
from app import oauth2

router = APIRouter()

@router.post("/save-token")
@router.post("/update-fcm-token")
@router.post("/users/save-token")
def save_token(
    data: TokenRequest,
    db: Session = Depends(get_db),
    current_user=Depends(oauth2.get_current_user)
):
    token_value = data.get_token()

    if not token_value:
        return {"message": "No token provided"}

    db.query(DeviceToken).filter(
        DeviceToken.token == token_value,
        DeviceToken.user_id != current_user.id
    ).delete()

    existing = db.query(DeviceToken).filter(
        DeviceToken.user_id == current_user.id,
        DeviceToken.token == token_value
    ).first()

    if not existing:
        db.add(DeviceToken(user_id=current_user.id, token=token_value))

    db.commit()
    return {"message": "Token saved successfully"}

#returns user notification history
@router.get("/notifications")
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user=Depends(oauth2.get_current_user)
):
    """Notification history for the logged-in user (newest first)."""
    notifs = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "data": n.data,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifs
    ]

#to mark as read
@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(oauth2.get_current_user)
):
    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if not n:
        return {"message": "Notification not found"}
    n.is_read = True
    db.commit()
    return {"message": "Marked as read"}

# Test notification
@router.post("/test-notify")
def test_notify(
    user_id: int,
    db: Session = Depends(get_db)
):
    tokens = db.query(DeviceToken).filter(DeviceToken.user_id == user_id).all()
    token_list = [t.token for t in tokens]

    if not token_list:
        return {"message": "No tokens found for user"}

    try:
        send_notification(token_list, "Test", "Hello from backend")
        return {"message": "Notification sent"}
    except Exception as e:
        return {"message": f"Notification skipped: {e}"}
    
@router.delete("/clear-tokens")
def clear_tokens(db: Session = Depends(get_db)):
    db.query(DeviceToken).delete()
    db.commit()
    return {"message": "All tokens cleared"}