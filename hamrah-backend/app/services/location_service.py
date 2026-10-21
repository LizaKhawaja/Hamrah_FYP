import httpx
from fastapi import WebSocket
from typing import Dict, List
import json

#take image from user and save it locally in upload folder and return url
class LocationManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, ride_id: int):
        await websocket.accept()

        if ride_id not in self.active_connections:
            self.active_connections[ride_id] = []

        self.active_connections[ride_id].append(websocket)

        print(f"Connected to ride {ride_id}")

    def disconnect(self, websocket: WebSocket, ride_id: int):
        if ride_id in self.active_connections:
            if websocket in self.active_connections[ride_id]:
                self.active_connections[ride_id].remove(websocket)

            if not self.active_connections[ride_id]:
                del self.active_connections[ride_id]

        print(f"Disconnected from ride {ride_id}")

    async def broadcast_location(self, ride_id: int, data: dict):
        if ride_id not in self.active_connections:
            return

        message = json.dumps(data)
        disconnected = []

        for connection in self.active_connections[ride_id]:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)

        for conn in disconnected:
            self.active_connections[ride_id].remove(conn)

location_manager = LocationManager()


async def get_eta(origin_lat, origin_lng, dest_lat, dest_lng) -> int | None:

    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
    )

    params = {
        "overview": "false",
        "annotations": "false"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10)
            data = response.json()

        if data.get("code") == "Ok":
            return int(data["routes"][0]["duration"])

    except Exception as e:
        print("OSRM error:", e)

    return None