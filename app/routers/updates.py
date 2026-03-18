from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.database import get_db
from app.models import RuntimeState, Task, Update, UpdateType, WorkflowState
from app.schemas import UpdateCreate, UpdateOut
from app.services.state import set_task_runtime_state, set_task_workflow_state
from app.ws import broadcast

router = APIRouter(prefix="/tasks/{task_id}/updates", tags=["updates"])


@router.post("", response_model=UpdateOut, status_code=201)
async def create_update(
    task_id: int,
    body: UpdateCreate,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    """Agent reports a progress update."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    update = Update(
        task_id=task_id,
        type=body.type,
        content=body.content,
        commit_sha=body.commit_sha,
        branch=body.branch,
    )
    db.add(update)

    if body.branch and body.type == UpdateType.commit:
        task.branch = body.branch

    if body.type == UpdateType.error:
        set_task_workflow_state(task, WorkflowState.failed, force=True)
        set_task_runtime_state(task, RuntimeState.failed)
        task.failure_reason = body.content

    if body.type == UpdateType.summary:
        set_task_workflow_state(task, WorkflowState.needs_review, force=True)
        set_task_runtime_state(task, RuntimeState.idle)
        task.result_summary = body.content

    await db.commit()
    await db.refresh(update)

    await broadcast(
        {
            "type": "new_update",
            "task_id": task_id,
            "update_type": body.type.value,
            "content": body.content,
        }
    )

    return update


@router.get("", response_model=None)
async def list_updates(
    task_id: int,
    type: Optional[UpdateType] = None,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    stmt = (
        select(Update)
        .where(Update.task_id == task_id)
        .order_by(Update.created_at)
    )
    if type:
        stmt = stmt.where(Update.type == type)
    result = await db.execute(stmt)
    return result.scalars().all()
