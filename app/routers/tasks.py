import asyncio
import json
import shlex
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.database import get_db
from app.models import (
    Message,
    MessageDirection,
    Priority,
    Role,
    Run,
    RunState,
    RunTriggerType,
    RuntimeState,
    RuntimeStatus,
    Task,
    TargetType,
    TaskKind,
    TaskStatus,
    ThreadState,
    Update,
    UpdateType,
    WorkflowState,
    default_target_type,
    infer_task_kind,
)
from app.schemas import (
    MessageCreate,
    MessageOut,
    RunOut,
    TaskCreate,
    TaskPatch,
)
from app.services.agent import AgentService
from app.services.adapters import adapter_for
from app.services.orchestration import build_role_prompt, handle_task_completion
from app.services.repo import (
    get_commits,
    get_diff_stats,
    get_file_diff,
    _detect_default_branch,
    _git,
)
from app.services.state import (
    infer_run_trigger,
    mark_run_state,
    set_task_runtime_state,
    set_task_workflow_state,
    sync_task_thread,
)
from app.ws import broadcast

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _task_out(task: Task, db: AsyncSession) -> dict:
    """Serialize a Task to a dict, including role_name."""
    data = {c.name: getattr(task, c.name) for c in task.__table__.columns}
    data["status"] = task.workflow_status.value
    if task.role_id:
        role = await db.get(Role, task.role_id)
        data["role_name"] = role.name if role else None
    else:
        data["role_name"] = None
    return data


async def _start_run_record(
    db: AsyncSession,
    task: Task,
    prompt: Optional[str],
    runner_id: str,
    *,
    trigger_type: RunTriggerType,
) -> Run:
    prompt_summary = prompt.strip()[:240] if prompt else None
    run = Run(
        task_id=task.id,
        thread_id=task.thread_id,
        runner_id=runner_id,
        provider=task.agent_type,
        trigger_type=trigger_type,
        status=RuntimeStatus.running,
        run_state=RunState.running,
        prompt=prompt,
        prompt_summary=prompt_summary,
        dispatch_snapshot=json.dumps(
            {
                "task_kind": task.task_kind.value,
                "target_type": task.target_type.value,
                "branch": task.branch,
                "base_branch": task.base_branch,
                "commit_start": task.commit_start,
                "commit_end": task.commit_end,
                "path_scope": task.path_scope,
                "workflow_state": task.workflow_state.value,
                "runtime_state": task.runtime_state.value,
            }
        ),
    )
    db.add(run)
    await db.flush()
    task.active_run_id = run.id
    return run


async def _finish_active_run(
    db: AsyncSession,
    task: Task,
    *,
    status: RuntimeStatus,
    runner_id: Optional[str] = None,
    exit_code: Optional[int] = None,
    error: Optional[str] = None,
    error_type: Optional[str] = None,
    output_summary: Optional[str] = None,
) -> None:
    runner_id = runner_id or task.runner_id
    if not runner_id:
        return
    stmt = (
        select(Run)
        .where(Run.task_id == task.id, Run.runner_id == runner_id)
        .order_by(Run.started_at.desc())
    )
    result = await db.execute(stmt)
    run = result.scalars().first()
    if not run:
        return
    mark_run_state(
        run,
        run_state=(
            RunState.failed
            if status == RuntimeStatus.failed
            else RunState.cancelled
            if status == RuntimeStatus.stopped
            else RunState.completed
        ),
        exit_code=exit_code,
        error=error,
        error_type=error_type,
        output_summary=output_summary,
    )
    run.finished_at = datetime.now(timezone.utc)
    task.active_run_id = None


@router.post("", response_model=None, status_code=201)
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    role = await db.get(Role, body.role_id) if body.role_id else None
    task_kind = body.task_kind or infer_task_kind(
        body.agent_type, role.name if role else None
    )
    target_type = body.target_type or default_target_type(body.branch, body.base_branch)
    task = Task(
        objective_id=body.objective_id,
        title=body.title,
        description=body.description,
        repo_url=body.repo_url,
        branch=body.branch,
        base_branch=body.base_branch,
        agent_type=body.agent_type,
        task_kind=task_kind,
        target_type=target_type,
        priority=body.priority,
        commit_start=body.commit_start,
        commit_end=body.commit_end,
        path_scope=body.path_scope,
        status=TaskStatus.pending,
        workflow_status=TaskStatus.pending,
        workflow_state=WorkflowState.ready,
        runtime_state=RuntimeState.idle,
        role_id=body.role_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await broadcast({"type": "task_created", "task_id": task.id, "title": task.title})
    return await _task_out(task, db)


@router.get("", response_model=None)
async def list_tasks(
    status: Optional[TaskStatus] = None,
    objective_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    stmt = select(Task).order_by(Task.created_at.desc())
    if status:
        stmt = stmt.where(Task.workflow_status == status)
    if objective_id is not None:
        stmt = stmt.where(Task.objective_id == objective_id)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return [await _task_out(t, db) for t in tasks]


@router.get("/{task_id}", response_model=None)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return await _task_out(task, db)


@router.patch("/{task_id}", response_model=None)
async def patch_task(
    task_id: int,
    body: TaskPatch,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if body.workflow_status is not None:
        mapping = {
            TaskStatus.pending: WorkflowState.ready,
            TaskStatus.paused: WorkflowState.waiting_for_user,
            TaskStatus.needs_review: WorkflowState.needs_review,
            TaskStatus.completed: WorkflowState.completed,
            TaskStatus.failed: WorkflowState.failed,
        }
        set_task_workflow_state(task, mapping[body.workflow_status], force=True)
    if body.workflow_state is not None:
        set_task_workflow_state(task, body.workflow_state, force=True)
    if body.runtime_status is not None:
        runtime_mapping = {
            RuntimeStatus.idle: RuntimeState.idle,
            RuntimeStatus.running: RuntimeState.running,
            RuntimeStatus.stopped: RuntimeState.stopped,
            RuntimeStatus.failed: RuntimeState.failed,
        }
        set_task_runtime_state(task, runtime_mapping[body.runtime_status])
    if body.runtime_state is not None:
        set_task_runtime_state(task, body.runtime_state)
    if body.task_kind is not None:
        task.task_kind = body.task_kind
    if body.target_type is not None:
        task.target_type = body.target_type
    if body.priority is not None:
        task.priority = body.priority
    if body.branch is not None:
        task.branch = body.branch
    if body.base_branch is not None:
        task.base_branch = body.base_branch
    if body.commit_start is not None:
        task.commit_start = body.commit_start
    if body.commit_end is not None:
        task.commit_end = body.commit_end
    if body.path_scope is not None:
        task.path_scope = body.path_scope
    if body.blocked_reason is not None:
        task.blocked_reason = body.blocked_reason
    if body.result_summary is not None:
        task.result_summary = body.result_summary
    if body.failure_reason is not None:
        task.failure_reason = body.failure_reason
    if body.next_action_hint is not None:
        task.next_action_hint = body.next_action_hint
    await db.commit()
    await db.refresh(task)
    await broadcast(
        {
            "type": "task_update",
            "task_id": task.id,
            "workflow_status": task.workflow_status.value,
            "runtime_status": task.runtime_status.value,
            "status": task.workflow_status.value,
        }
    )
    return await _task_out(task, db)


class StartRequest(BaseModel):
    prompt: Optional[str] = None


@router.post("/{task_id}/start", response_model=None)
async def start_task(
    task_id: int,
    body: Optional[StartRequest] = None,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    """Start or resume an agent run for this task."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.runtime_status == RuntimeStatus.running:
        raise HTTPException(400, "Task is already running")

    prompt = body.prompt if body else None
    adapter = adapter_for(task)

    role_prompt = await build_role_prompt(db, task)

    try:
        set_task_runtime_state(task, RuntimeState.starting)
        set_task_workflow_state(task, WorkflowState.in_progress)
        runner_id = await adapter.start(task, prompt=prompt, role_prompt=role_prompt)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except FileNotFoundError:
        raise HTTPException(
            400, f"Agent CLI '{task.agent_type}' not found on this machine"
        )
    task.runner_id = runner_id
    set_task_runtime_state(task, RuntimeState.running)
    task.last_run_started_at = datetime.now(timezone.utc)
    task.last_heartbeat_at = task.last_run_started_at
    await sync_task_thread(db, task, thread_state=ThreadState.active)
    await _start_run_record(
        db,
        task,
        prompt,
        runner_id,
        trigger_type=infer_run_trigger(task),
    )
    await db.commit()
    await db.refresh(task)
    await broadcast(
        {
            "type": "task_update",
            "task_id": task.id,
            "workflow_status": task.workflow_status.value,
            "runtime_status": task.runtime_status.value,
            "status": task.workflow_status.value,
        }
    )
    return await _task_out(task, db)


@router.post("/{task_id}/stop", response_model=None)
async def stop_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    runner_id = task.runner_id or AgentService.runner_id(task)
    await adapter_for(task).stop(task)
    await _finish_active_run(
        db, task, status=RuntimeStatus.stopped, runner_id=runner_id
    )
    await db.commit()
    await db.refresh(task)
    await broadcast(
        {
            "type": "task_update",
            "task_id": task.id,
            "workflow_status": task.workflow_status.value,
            "runtime_status": task.runtime_status.value,
            "status": task.workflow_status.value,
        }
    )
    return await _task_out(task, db)


# --- Live run output ---


@router.get("/{task_id}/output")
async def get_output(
    task_id: int,
    lines: int = 80,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    adapter = adapter_for(task)
    alive = await adapter.is_alive(task)
    task.last_heartbeat_at = datetime.now(timezone.utc)
    output = await adapter.capture_output(task, lines)

    ended = False
    if task.runtime_status == RuntimeStatus.running and not alive:
        finished_runner_id = task.runner_id or AgentService.runner_id(task)
        exit_code = AgentService.consume_exit_code(finished_runner_id)
        run_status = (
            RuntimeStatus.failed if exit_code not in (0, None) else RuntimeStatus.idle
        )
        records = adapter.finalize_records(task, output)
        await handle_task_completion(db, task, records)
        for record in records:
            db.add(record)
        if run_status == RuntimeStatus.failed:
            set_task_workflow_state(task, WorkflowState.failed, force=True)
            task.failure_reason = output.strip() or "Agent run failed"
            if output.strip():
                db.add(
                    Update(
                        task_id=task.id,
                        type=UpdateType.error,
                        content=output.strip(),
                        branch=task.branch,
                    )
                )
        await _finish_active_run(
            db,
            task,
            status=run_status,
            runner_id=finished_runner_id,
            exit_code=exit_code,
            error=task.failure_reason,
            error_type="agent_run_failed" if run_status == RuntimeStatus.failed else None,
            output_summary=output.strip()[:500] if output else None,
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
        await db.commit()
        ended = True

    await db.commit()
    return {"task_id": task.id, "alive": alive, "ended": ended, "output": output}


# --- Push approval flow ---


class PushApproval(BaseModel):
    approve: bool


@router.post("/{task_id}/push", response_model=None)
async def approve_push(
    task_id: int,
    body: PushApproval,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.workflow_status != TaskStatus.needs_review:
        raise HTTPException(400, "Task is not awaiting review")
    if not task.branch:
        raise HTTPException(400, "No branch set for this task")

    if body.approve:
        cmd = f"git -C {shlex.quote(task.repo_url)} push origin {shlex.quote(task.branch)}"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode().strip()
            update = Update(
                task_id=task.id,
                type=UpdateType.error,
                content=f"Push failed: {error_msg}",
                branch=task.branch,
            )
            db.add(update)
            await db.commit()
            raise HTTPException(500, f"Push failed: {error_msg}")

        set_task_workflow_state(task, WorkflowState.completed, force=True)
        update = Update(
            task_id=task.id,
            type=UpdateType.summary,
            content=f"Branch {task.branch} pushed to origin.",
            branch=task.branch,
        )
        db.add(update)
    else:
        set_task_workflow_state(task, WorkflowState.waiting_for_user, force=True)
        update = Update(
            task_id=task.id,
            type=UpdateType.summary,
            content="Push rejected by user. Task paused for further work.",
        )
        db.add(update)

    await db.commit()
    await db.refresh(task)
    await broadcast(
        {
            "type": "task_update",
            "task_id": task.id,
            "workflow_status": task.workflow_status.value,
            "runtime_status": task.runtime_status.value,
            "status": task.workflow_status.value,
        }
    )
    return await _task_out(task, db)


# --- Diff & review endpoints ---


@router.get("/{task_id}/diff")
async def get_diff(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    """Get diff stats and full diff for the agent's branch vs base."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if not task.branch:
        raise HTTPException(400, "No branch set")

    repo_path = task.repo_url
    base = task.base_branch or await _detect_default_branch(repo_path)

    # Get structured diff stats
    stats = await get_diff_stats(repo_path, base, task.branch)

    # Get full diff
    code, full_diff, stderr = await _git(
        repo_path, "diff", f"{base}..{task.branch}",
    )
    if code != 0:
        raise HTTPException(500, f"Diff failed: {stderr}")

    return {
        "task_id": task.id,
        "branch": task.branch,
        "base": base,
        "diff": full_diff,
        "stats": stats,
    }


@router.get("/{task_id}/diff/{file_path:path}")
async def get_single_file_diff(
    task_id: int,
    file_path: str,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    """Get diff for a single file."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if not task.branch:
        raise HTTPException(400, "No branch set")

    repo_path = task.repo_url
    base = task.base_branch or await _detect_default_branch(repo_path)
    diff = await get_file_diff(repo_path, base, task.branch, file_path)

    return {"file": file_path, "diff": diff}


@router.get("/{task_id}/commits")
async def get_task_commits(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    """Get commit log for this task's branch."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if not task.branch:
        return []

    repo_path = task.repo_url
    base = task.base_branch or await _detect_default_branch(repo_path)
    return await get_commits(repo_path, base, task.branch)


# --- Messages (follow-up instructions) ---


@router.post("/{task_id}/messages", response_model=MessageOut, status_code=201)
async def send_message(
    task_id: int,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    msg = Message(
        task_id=task_id,
        direction=body.direction,
        content=body.content,
    )
    db.add(msg)

    if body.direction == MessageDirection.user_to_agent:
        try:
            new_runner = await adapter_for(task).send_message(task, body.content)
            if new_runner:
                task.runner_id = new_runner
            set_task_workflow_state(task, WorkflowState.in_progress, force=True)
            set_task_runtime_state(task, RuntimeState.running)
            task.last_run_started_at = datetime.now(timezone.utc)
            task.last_heartbeat_at = task.last_run_started_at
            await sync_task_thread(
                db,
                task,
                thread_state=ThreadState.active,
                touch_message_time=True,
            )
            await _start_run_record(
                db,
                task,
                body.content,
                task.runner_id or AgentService.runner_id(task),
                trigger_type=RunTriggerType.message,
            )
        except RuntimeError as e:
            raise HTTPException(400, str(e))

    await db.commit()
    await db.refresh(msg)
    await broadcast(
        {
            "type": "new_message",
            "task_id": task_id,
            "direction": body.direction.value,
            "content": body.content,
        }
    )
    if body.direction == MessageDirection.user_to_agent:
        await broadcast(
            {
                "type": "task_update",
                "task_id": task.id,
                "workflow_status": task.workflow_status.value,
                "runtime_status": task.runtime_status.value,
                "status": task.workflow_status.value,
            }
        )
    return msg


@router.get("/{task_id}/runs", response_model=list[RunOut])
async def list_runs(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    stmt = select(Run).where(Run.task_id == task_id).order_by(Run.started_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{task_id}/messages", response_model=None)
async def list_messages(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    stmt = (
        select(Message)
        .where(Message.task_id == task_id)
        .order_by(Message.created_at)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
