"""
WebSocket Connection Manager and Stream Broadcaster.
Handles real-time bi-directional telemetry streaming to frontend clients.
"""

import json
from typing import List, Set
from fastapi import WebSocket, WebSocketDisconnect

class WebSocketManager:
    """Manages active WebSocket client connections for real-time telemetry streaming."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Accepts and registers a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Removes a disconnected WebSocket client."""
        self.active_connections.discard(websocket)

    async def broadcast_json(self, data: dict) -> None:
        """Broadcasts a JSON dictionary payload to all active clients."""
        dead_connections = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)

ws_manager = WebSocketManager()

