from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.database import get_db
from app.models import Objective, ObjectiveState
from app.schemas import ObjectiveCreate, ObjectiveOut, ObjectivePatch
from app.services.orchestration import dispatch_task_run, ensure_orchestrator_task
from app.ws import broadcast

router = APIRouter(prefix="/objectives", tags=["objectives"])


@router.post("", response_model=ObjectiveOut, status_code=201)
async def create_objective(
    body: ObjectiveCreate,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    objective = Objective(
        title=body.title,
        description=body.description,
        repo_url=body.repo_url,
        priority=body.priority,
        created_by=user,
    )
    db.add(objective)
    await db.flush()
    orchestrator = await ensure_orchestrator_task(
        db, objective, agent_type=body.agent_type
    )
    await dispatch_task_run(db, orchestrator, prompt=body.description or body.title)
    objective.objective_state = ObjectiveState.active
    await db.commit()
    await db.refresh(objective)
    await broadcast(
        {"type": "objective_created", "objective_id": objective.id, "title": objective.title}
    )
    return objective


@router.get("", response_model=list[ObjectiveOut])
async def list_objectives(
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    result = await db.execute(select(Objective).order_by(Objective.updated_at.desc()))
    return result.scalars().all()


@router.get("/{objective_id}", response_model=ObjectiveOut)
async def get_objective(
    objective_id: int,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    objective = await db.get(Objective, objective_id)
    if not objective:
        raise HTTPException(404, "Objective not found")
    return objective


@router.patch("/{objective_id}", response_model=ObjectiveOut)
async def patch_objective(
    objective_id: int,
    body: ObjectivePatch,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    objective = await db.get(Objective, objective_id)
    if not objective:
        raise HTTPException(404, "Objective not found")
    for field in (
        "title",
        "description",
        "repo_url",
        "priority",
        "objective_state",
        "summary",
        "recommended_next_action",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(objective, field, value)
    await db.commit()
    await db.refresh(objective)
    return objective
