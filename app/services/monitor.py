import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import async_session
from app.models import Run, RuntimeStatus, Task, TaskStatus, Update, UpdateType
from app.services.agent import AgentService
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
                stmt = select(Task).where(Task.runtime_status == RuntimeStatus.running)
                result = await db.execute(stmt)
                tasks = result.scalars().all()

                for task in tasks:
                    adapter = adapter_for(task)
                    alive = await adapter.is_alive(task)
                    if not alive:
                        finished_runner_id = task.runner_id or AgentService.runner_id(task)
                        exit_code = AgentService.consume_exit_code(finished_runner_id)
                        run_status = (
                            RuntimeStatus.failed
                            if exit_code not in (0, None)
                            else RuntimeStatus.idle
                        )
                        logger.info(
                            "Task %d agent run ended (runner %s)",
                            task.id,
                            finished_runner_id,
                        )
                        last_output = ""
                        try:
                            last_output = await adapter.capture_output(task)
                        except Exception:
                            pass

                        for record in adapter.finalize_records(task, last_output):
                            db.add(record)
                        if run_status == RuntimeStatus.failed:
                            task.workflow_status = TaskStatus.failed
                            task.status = TaskStatus.failed
                            if last_output.strip():
                                db.add(
                                    Update(
                                        task_id=task.id,
                                        type=UpdateType.error,
                                        content=last_output.strip(),
                                        branch=task.branch,
                                    )
                                )
                        task.runtime_status = run_status
                        stmt = (
                            select(Run)
                            .where(
                                Run.task_id == task.id,
                                Run.runner_id == finished_runner_id,
                            )
                            .order_by(Run.started_at.desc())
                        )
                        result = await db.execute(stmt)
                        run = result.scalars().first()
                        if run:
                            run.status = run_status
                            run.exit_code = exit_code
                            run.finished_at = datetime.now(timezone.utc)
                        await db.commit()

                        # Notify connected clients
                        await broadcast(
                            {
                                "type": "task_update",
                                "task_id": task.id,
                                "workflow_status": task.workflow_status.value,
                                "runtime_status": task.runtime_status.value,
                                "status": task.workflow_status.value,
                                "message": "Agent run ended",
                            }
                        )
        except Exception:
            logger.exception("Monitor loop error")

        await asyncio.sleep(POLL_INTERVAL)
