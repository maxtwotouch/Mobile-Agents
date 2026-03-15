import asyncio
import shlex
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.database import get_db
from app.models import Message, MessageDirection, Task, TaskStatus, Update, UpdateType
from app.schemas import (
    MessageCreate,
    MessageOut,
    TaskCreate,
    TaskOut,
    TaskPatch,
)
from app.services.agent import AgentService
from app.services.adapters import adapter_for
from app.ws import broadcast

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    task = Task(
        title=body.title,
        description=body.description,
        repo_url=body.repo_url,
        branch=body.branch,
        agent_type=body.agent_type,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await broadcast({"type": "task_created", "task_id": task.id, "title": task.title})
    return task


@router.get("", response_model=None)
async def list_tasks(
    status: Optional[TaskStatus] = None,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    stmt = select(Task).order_by(Task.created_at.desc())
    if status:
        stmt = stmt.where(Task.status == status)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskOut)
async def patch_task(
    task_id: int,
    body: TaskPatch,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if body.status is not None:
        task.status = body.status
    if body.branch is not None:
        task.branch = body.branch
    await db.commit()
    await db.refresh(task)
    await broadcast(
        {"type": "task_update", "task_id": task.id, "status": task.status.value}
    )
    return task


@router.post("/{task_id}/start", response_model=TaskOut)
async def start_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    """Spawn an agent in a tmux session for this task."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status == TaskStatus.running:
        raise HTTPException(400, "Task is already running")

    adapter = adapter_for(task)
    try:
        session_name = await adapter.start(task)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except FileNotFoundError:
        raise HTTPException(
            400, f"Agent CLI '{task.agent_type}' not found on this machine"
        )
    task.tmux_session = session_name
    task.status = TaskStatus.running
    await db.commit()
    await db.refresh(task)
    await broadcast(
        {"type": "task_update", "task_id": task.id, "status": "running"}
    )
    return task


@router.post("/{task_id}/stop", response_model=TaskOut)
async def stop_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    """Kill the tmux session for this task."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    await adapter_for(task).stop(task)
    await db.commit()
    await db.refresh(task)
    await broadcast(
        {"type": "task_update", "task_id": task.id, "status": "paused"}
    )
    return task


# --- Live tmux output ---


@router.get("/{task_id}/output")
async def get_output(
    task_id: int,
    lines: int = 80,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    """Capture live terminal output from the agent's tmux session."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if not task.tmux_session:
        raise HTTPException(400, "No active tmux session")

    adapter = adapter_for(task)
    alive = await adapter.is_alive(task)
    output = await adapter.capture_output(task, lines)

    if not alive:
        for record in adapter.finalize_records(task, output):
            db.add(record)
        await db.commit()
        raise HTTPException(409, "Agent session ended")

    return {"task_id": task.id, "alive": alive, "output": output}


# --- Push approval flow ---


class PushApproval(BaseModel):
    approve: bool


@router.post("/{task_id}/push", response_model=TaskOut)
async def approve_push(
    task_id: int,
    body: PushApproval,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    """Approve or reject pushing the agent's branch."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status != TaskStatus.needs_review:
        raise HTTPException(400, "Task is not awaiting review")
    if not task.branch:
        raise HTTPException(400, "No branch set for this task")

    if body.approve:
        # Push the branch
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

        task.status = TaskStatus.completed
        update = Update(
            task_id=task.id,
            type=UpdateType.summary,
            content=f"Branch {task.branch} pushed to origin. Output: {stdout.decode().strip()}",
            branch=task.branch,
        )
        db.add(update)
    else:
        task.status = TaskStatus.paused
        update = Update(
            task_id=task.id,
            type=UpdateType.summary,
            content="Push rejected by user. Task paused for further work.",
        )
        db.add(update)

    await db.commit()
    await db.refresh(task)
    await broadcast(
        {"type": "task_update", "task_id": task.id, "status": task.status.value}
    )
    return task


# --- Diff preview (for review before push) ---


@router.get("/{task_id}/diff")
async def get_diff(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    """Get the git diff for the agent's branch vs main."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if not task.branch:
        raise HTTPException(400, "No branch set")

    # Get the default branch
    cmd_default = f"git -C {shlex.quote(task.repo_url)} symbolic-ref refs/remotes/origin/HEAD --short"
    proc = await asyncio.create_subprocess_shell(
        cmd_default,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    default_branch = stdout.decode().strip().replace("origin/", "") if proc.returncode == 0 else "main"

    # Get diff
    cmd = f"git -C {shlex.quote(task.repo_url)} diff {shlex.quote(default_branch)}..{shlex.quote(task.branch)}"
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise HTTPException(500, f"Diff failed: {stderr.decode().strip()}")

    return {
        "task_id": task.id,
        "branch": task.branch,
        "base": default_branch,
        "diff": stdout.decode(),
    }


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
            new_session = await adapter_for(task).send_message(task, body.content)
            if new_session:
                task.tmux_session = new_session
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
    return msg


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
