from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Run,
    RunState,
    RunTriggerType,
    RuntimeState,
    Task,
    Thread,
    ThreadState,
    WorkflowState,
    legacy_runtime_status_for_runtime,
)


ALLOWED_WORKFLOW_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.draft: {WorkflowState.ready, WorkflowState.cancelled},
    WorkflowState.ready: {
        WorkflowState.in_progress,
        WorkflowState.blocked,
        WorkflowState.waiting_for_user,
        WorkflowState.cancelled,
        WorkflowState.failed,
    },
    WorkflowState.in_progress: {
        WorkflowState.needs_review,
        WorkflowState.waiting_for_user,
        WorkflowState.blocked,
        WorkflowState.failed,
        WorkflowState.cancelled,
    },
    WorkflowState.waiting_for_user: {
        WorkflowState.ready,
        WorkflowState.in_progress,
        WorkflowState.blocked,
        WorkflowState.cancelled,
        WorkflowState.failed,
    },
    WorkflowState.blocked: {
        WorkflowState.ready,
        WorkflowState.waiting_for_user,
        WorkflowState.cancelled,
        WorkflowState.failed,
    },
    WorkflowState.needs_review: {
        WorkflowState.approved,
        WorkflowState.in_progress,
        WorkflowState.failed,
        WorkflowState.cancelled,
    },
    WorkflowState.approved: {
        WorkflowState.completed,
        WorkflowState.in_progress,
        WorkflowState.cancelled,
    },
    WorkflowState.completed: set(),
    WorkflowState.failed: set(),
    WorkflowState.cancelled: set(),
}


def set_task_workflow_state(task: Task, state: WorkflowState, *, force: bool = False) -> None:
    current = task.workflow_state
    if not force and current != state and state not in ALLOWED_WORKFLOW_TRANSITIONS[current]:
        raise ValueError(f"Invalid workflow transition: {current.value} -> {state.value}")
    task.set_workflow_state(state)


def set_task_runtime_state(task: Task, state: RuntimeState) -> None:
    task.set_runtime_state(state)


def mark_run_state(
    run: Run,
    *,
    run_state: RunState,
    exit_code: int | None = None,
    error: str | None = None,
    error_type: str | None = None,
    output_summary: str | None = None,
) -> None:
    run.run_state = run_state
    if run_state == RunState.failed:
        run.status = task_runtime_legacy(RuntimeState.failed)
    elif run_state == RunState.cancelled:
        run.status = task_runtime_legacy(RuntimeState.stopped)
    elif run_state in {RunState.queued, RunState.starting, RunState.running}:
        run.status = task_runtime_legacy(RuntimeState.running)
    else:
        run.status = task_runtime_legacy(RuntimeState.idle)
    run.exit_code = exit_code
    run.error = error
    run.error_type = error_type
    run.output_summary = output_summary


def task_runtime_legacy(state: RuntimeState):
    return legacy_runtime_status_for_runtime(state)


def infer_run_trigger(task: Task) -> RunTriggerType:
    if task.thread_id or task.codex_session_id:
        return RunTriggerType.resume
    return RunTriggerType.manual_start


async def sync_task_thread(
    db: AsyncSession,
    task: Task,
    *,
    thread_state: ThreadState,
    touch_message_time: bool = False,
) -> None:
    stmt = select(Thread).where(Thread.task_id == task.id)
    result = await db.execute(stmt)
    thread = result.scalars().first()
    if not thread:
        thread = Thread(
            task_id=task.id,
            provider=task.agent_type,
            provider_thread_id=task.thread_id or task.codex_session_id,
            thread_state=thread_state,
        )
        db.add(thread)
    else:
        thread.provider = task.agent_type
        thread.provider_thread_id = task.thread_id or task.codex_session_id
        thread.thread_state = thread_state
    if touch_message_time:
        thread.last_message_at = datetime.now(timezone.utc)
