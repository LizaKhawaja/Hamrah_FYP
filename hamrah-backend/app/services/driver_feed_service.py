import json
from typing import Dict, List

from fastapi import WebSocket


class DriverFeedManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, driver_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(driver_id, []).append(websocket)
        print(f"[DRIVER-FEED] Driver {driver_id} connected")

    def disconnect(self, driver_id: int, websocket: WebSocket):
        connections = self.active_connections.get(driver_id)
        if not connections:
            return

        if websocket in connections:
            connections.remove(websocket)

        if not connections:
            del self.active_connections[driver_id]

        print(f"[DRIVER-FEED] Driver {driver_id} disconnected")

    async def send_to_driver(self, driver_id: int, data: dict):
        connections = self.active_connections.get(driver_id)
        if not connections:
            return

        message = json.dumps(data, default=str)
        disconnected = []

        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            if connection in connections:
                connections.remove(connection)

        if not connections:
            self.active_connections.pop(driver_id, None)


driver_feed_manager = DriverFeedManager()
