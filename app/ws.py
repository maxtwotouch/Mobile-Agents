import json
import logging
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger("ws")

# Connected WebSocket clients
_clients: Set[WebSocket] = set()


async def connect(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    logger.info("WebSocket client connected (%d total)", len(_clients))


def disconnect(ws: WebSocket):
    _clients.discard(ws)
    logger.info("WebSocket client disconnected (%d total)", len(_clients))


async def broadcast(data: Dict):
    """Send a JSON message to all connected WebSocket clients."""
    global _clients
    message = json.dumps(data)
    dead = set()
    for ws in _clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    _clients -= dead
