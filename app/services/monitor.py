import asyncio
import logging

from sqlalchemy import select

from app.database import async_session
from app.models import Task, TaskStatus
from app.services.adapters import adapter_for
from app.ws import broadcast

logger = logging.getLogger("monitor")

# How often to check running tasks (seconds)
POLL_INTERVAL = 15


async def monitor_loop():
    """Background loop that checks if running agents are still alive."""
    while True:
        try:
            async with async_session() as db:
                stmt = select(Task).where(Task.status == TaskStatus.running)
                result = await db.execute(stmt)
                tasks = result.scalars().all()

                for task in tasks:
                    if not task.tmux_session:
                        continue

                    adapter = adapter_for(task)
                    alive = await adapter.is_alive(task)
                    if not alive:
                        logger.info(
                            "Task %d agent died (session %s)",
                            task.id,
                            task.tmux_session,
                        )
                        last_output = ""
                        try:
                            last_output = await adapter.capture_output(task)
                        except Exception:
                            pass

                        for record in adapter.finalize_records(task, last_output):
                            db.add(record)
                        await db.commit()

                        # Notify connected clients
                        await broadcast(
                            {
                                "type": "task_update",
                                "task_id": task.id,
                                "status": task.status.value,
                                "message": "Agent session ended",
                            }
                        )
        except Exception:
            logger.exception("Monitor loop error")

        await asyncio.sleep(POLL_INTERVAL)
