import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import async_session
from app.models import (
    Run,
    RunState,
    RuntimeState,
    RuntimeStatus,
    Task,
    ThreadState,
    Update,
    UpdateType,
    WorkflowState,
)
from app.services.agent import AgentService
from app.services.adapters import adapter_for
from app.services.orchestration import handle_task_completion
from app.services.state import (
    mark_run_state,
    set_task_runtime_state,
    set_task_workflow_state,
    sync_task_thread,
)
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

                        records = adapter.finalize_records(task, last_output)
                        await handle_task_completion(db, task, records)
                        for record in records:
                            db.add(record)
                        if run_status == RuntimeStatus.failed:
                            set_task_workflow_state(task, WorkflowState.failed, force=True)
                            task.failure_reason = last_output.strip() or "Agent run failed"
                            if last_output.strip():
                                db.add(
                                    Update(
                                        task_id=task.id,
                                        type=UpdateType.error,
                                        content=last_output.strip(),
                                        branch=task.branch,
                                    )
                                )
                        set_task_runtime_state(
                            task,
                            RuntimeState.failed if run_status == RuntimeStatus.failed else RuntimeState.idle,
                        )
                        await sync_task_thread(
                            db,
                            task,
                            thread_state=ThreadState.failed
                            if run_status == RuntimeStatus.failed
                            else ThreadState.idle,
                        )
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
                            mark_run_state(
                                run,
                                run_state=RunState.failed
                                if run_status == RuntimeStatus.failed
                                else RunState.completed,
                                exit_code=exit_code,
                                error=task.failure_reason,
                                error_type="agent_run_failed"
                                if run_status == RuntimeStatus.failed
                                else None,
                                output_summary=last_output.strip()[:500] if last_output else None,
                            )
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
