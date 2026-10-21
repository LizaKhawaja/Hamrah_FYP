from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from .. import models, database, oauth2
from firebase_admin import messaging
import json
from typing import Dict, List

router = APIRouter(prefix="/calls", tags=["Calls"])

class SignalingRoom:

    def __init__(self):        self._rooms: Dict[int, List[tuple]] = {}

    #add user in signaling room/call room 
    async def join(self, ride_id: int, user_id: int, ws: WebSocket):
        if ride_id not in self._rooms:
            self._rooms[ride_id] = []
        self._rooms[ride_id].append((user_id, ws))
        if len(self._rooms[ride_id]) > 1:
            await ws.send_json({"type": "peer_ready"})
        else:
            await ws.send_json({"type": "waiting_for_peer"})

    #remove user from room when call is disconnected
    def leave(self, ride_id: int, ws: WebSocket):  
        if ride_id not in self._rooms:
            return
        self._rooms[ride_id] = [(uid, w) for uid, w in self._rooms[ride_id] if w != ws]
        if not self._rooms[ride_id]:
            del self._rooms[ride_id]

    #for message forwarding
    async def relay(self, ride_id: int, sender_ws: WebSocket, message: dict):
        if ride_id not in self._rooms:
            return
        for uid, ws in self._rooms[ride_id]:
            if ws != sender_ws:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass


signaling_room = SignalingRoom()

#for real time connection esablishment
@router.websocket("/ws/{ride_id}")
async def call_signaling_ws(websocket: WebSocket, ride_id: int):

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        token_data = oauth2.verify_access_token(
            token,
            HTTPException(status_code=403, detail="Invalid token")
        )
        user_id = token_data.id
    except Exception:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await signaling_room.join(ride_id, user_id, websocket)
    print(f"[CALL-WS] User {user_id} joined signaling room for ride {ride_id}")

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            print(f"[CALL-WS] Relay {data.get('type')} from user {user_id}")
            await signaling_room.relay(ride_id, websocket, data)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[CALL-WS] Error: {e}")
    finally:
        signaling_room.leave(ride_id, websocket)
        try:
            await signaling_room.relay(ride_id, websocket, {"type": "hangup"})
        except Exception:
            pass
        print(f"[CALL-WS] User {user_id} left signaling room for ride {ride_id}")

#send call notification to other user through firebase
@router.post("/notify")
def notify_call(
    ride_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    ride = db.query(models.Ride).filter(models.Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    is_driver = ride.driver_id == current_user.id

    if not is_driver:
        req = db.query(models.RideRequest).filter(
            models.RideRequest.ride_id == ride_id,
            models.RideRequest.passenger_id == current_user.id,
        ).first()
        if not req:
            raise HTTPException(status_code=403, detail="You are not part of this ride")

    caller_name = f"{current_user.first_name} {current_user.last_name}"

    if is_driver:
        accepted = db.query(models.RideRequest).filter(
            models.RideRequest.ride_id == ride_id,
            models.RideRequest.status.in_(["accepted", "picked_up", "riding"]),
        ).all()
        other_ids = [r.passenger_id for r in accepted]
    else:
        other_ids = [ride.driver_id]

    device_tokens = db.query(models.DeviceToken).filter(
        models.DeviceToken.user_id.in_(other_ids)
    ).all()

    token_list = [t.token for t in device_tokens]

    print("========== CALL NOTIFY DEBUG ==========")
    print("Current user:", current_user.id)
    print("Ride driver:", ride.driver_id)
    print("Is driver:", is_driver)
    print("Other user IDs:", other_ids)
    print("Token count:", len(token_list))
    print("=======================================")

    if token_list:
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title="Incoming Call 📞",
                body=f"{caller_name} is calling you",
            ),
            data={
                "type": "incoming_call",
                "caller_name": caller_name,
                "ride_id": str(ride_id),
            },
            tokens=token_list,
        )
        try:
            response = messaging.send_each_for_multicast(message)
            print("[CALL] FCM response:", response.success_count, "success,", response.failure_count, "failed")
        except Exception as e:
            print(f"[CALL] FCM notification skipped: {e}")
    else:
        print("[CALL] No token found for receiver")

    return {"status": "notified", "ride_id": ride_id, "caller": caller_name}

#user has accepted call
@router.post("/accept")
def accept_call(
    ride_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    ride = db.query(models.Ride).filter(models.Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    return {"status": "accepted", "ride_id": ride_id}
