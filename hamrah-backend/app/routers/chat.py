from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, oauth2
from pydantic import BaseModel
from ..services.fcm_service import send_notification

router = APIRouter(prefix="/chat", tags=["Chat"])


class SendMessageRequest(BaseModel):
    ride_id: int
    message: str


#fetch all messages of a ride to show history
@router.get("/{ride_id}/messages")
def get_messages(
    ride_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(oauth2.get_current_user)
):
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.ride_id == ride_id
    ).order_by(models.ChatMessage.created_at.asc()).all()

    return [
        {
            'id':       m.id,
            'text':     m.message,
            'from_me':  m.sender_id == current_user.id,
            'sender_id': m.sender_id,
            'sender_name': f"{m.sender.first_name} {m.sender.last_name}" if m.sender else '',
            'time':     m.created_at.isoformat() if m.created_at else '',
        }
        for m in messages
    ]

#save messages in db and notify other user about message
@router.post("/send")
def send_message(
    data: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user=Depends(oauth2.get_current_user)
):
    ride = db.query(models.Ride).filter(models.Ride.id == data.ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    msg = models.ChatMessage(
        ride_id=data.ride_id,
        sender_id=current_user.id,
        message=data.message,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    try:
        if current_user.id == ride.driver_id:
            requests = db.query(models.RideRequest).filter(
                models.RideRequest.ride_id == data.ride_id,
                models.RideRequest.status.in_(["accepted", "picked_up", "riding"])
            ).all()

            for req in requests:
                tokens = [
                    t.token for t in db.query(models.DeviceToken).filter(
                        models.DeviceToken.user_id == req.passenger_id
                    ).all()
                ]

                if tokens:
                    send_notification(
                        tokens,
                        title=f"New message from {current_user.first_name}",
                        body=data.message
                    )

        else:
            tokens = [
                t.token for t in db.query(models.DeviceToken).filter(
                    models.DeviceToken.user_id == ride.driver_id
                ).all()
            ]

            if tokens:
                send_notification(
                    tokens,
                    title=f"New message from {current_user.first_name}",
                    body=data.message
                )

    except Exception as e:
        print(f"Chat notification failed: {e}")

    return {
        "id": msg.id,
        "text": msg.message,
        "from_me": True,
        "sender_id": msg.sender_id,
        "time": msg.created_at.isoformat() if msg.created_at else "",
    }