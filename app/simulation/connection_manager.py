from fastapi import WebSocket
from typing import List, Dict


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, world_id: int):

        await websocket.accept()

        if world_id not in self.active_connections:
            self.active_connections[world_id] = []

        self.active_connections[world_id].append(websocket)

    def disconnect(self, websocket: WebSocket, world_id: int):

        if world_id in self.active_connections:

            self.active_connections[world_id].remove(websocket)

    async def broadcast(self, message: str, world_id: int):

        if world_id in self.active_connections:

            for connection in self.active_connections[world_id]:

                await connection.send_text(message)


manager = ConnectionManager()
