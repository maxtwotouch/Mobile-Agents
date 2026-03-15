import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.auth import verify_token
from app.database import engine, run_startup_migrations
from app.models import Base
from app.routers import auth, tasks, updates
from app.services.monitor import monitor_loop
from app.ws import connect, disconnect

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_startup_migrations()
    # Start background monitor
    monitor_task = asyncio.create_task(monitor_loop())
    yield
    monitor_task.cancel()


app = FastAPI(title="Mobile Agents", version="0.1.0", lifespan=lifespan)

app.include_router(auth.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(updates.router, prefix="/api")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket for real-time updates. Send token as first message to auth."""
    await connect(ws)
    try:
        # Expect token as first message (or skip if auth disabled)
        import os

        if os.environ.get("MA_AUTH_DISABLED") != "1":
            token_msg = await asyncio.wait_for(ws.receive_text(), timeout=10)
            user = verify_token(token_msg)
            if not user:
                await ws.send_json({"type": "error", "message": "Invalid token"})
                await ws.close(code=4001)
                return
            await ws.send_json({"type": "authenticated", "user": user})
        else:
            await ws.send_json({"type": "authenticated", "user": "admin"})

        # Keep alive — listen for pings or client messages
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except asyncio.TimeoutError:
        await ws.close(code=4002)
    finally:
        disconnect(ws)


app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
async def index():
    return FileResponse("frontend/index.html")
