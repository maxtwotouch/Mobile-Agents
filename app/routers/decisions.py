import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.database import get_db
from app.models import Decision, DecisionState
from app.schemas import DecisionAnswer, DecisionCreate
from app.services.orchestration import resume_orchestrator_from_decision
from app.ws import broadcast

router = APIRouter(prefix="/decisions", tags=["decisions"])


def _decision_out(decision: Decision) -> dict:
    options = None
    if decision.options:
        try:
            options = json.loads(decision.options)
        except json.JSONDecodeError:
            options = None
    return {
        "id": decision.id,
        "objective_id": decision.objective_id,
        "task_id": decision.task_id,
        "decision_type": decision.decision_type,
        "decision_state": decision.decision_state,
        "question": decision.question,
        "options": options,
        "recommended_option": decision.recommended_option,
        "chosen_option": decision.chosen_option,
        "answered_by": decision.answered_by,
        "answered_at": decision.answered_at,
        "created_at": decision.created_at,
    }


@router.post("", response_model=None, status_code=201)
async def create_decision(
    body: DecisionCreate,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    if not body.objective_id and not body.task_id:
        raise HTTPException(400, "Decision must belong to an objective or task")
    decision = Decision(
        objective_id=body.objective_id,
        task_id=body.task_id,
        decision_type=body.decision_type,
        question=body.question,
        options=json.dumps(body.options) if body.options is not None else None,
        recommended_option=body.recommended_option,
    )
    db.add(decision)
    await db.commit()
    await db.refresh(decision)
    await broadcast(
        {
            "type": "decision_created",
            "decision_id": decision.id,
            "task_id": decision.task_id,
            "objective_id": decision.objective_id,
            "question": decision.question,
        }
    )
    return _decision_out(decision)


@router.get("", response_model=None)
async def list_decisions(
    objective_id: Optional[int] = None,
    task_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    stmt = select(Decision).order_by(Decision.created_at.desc())
    if objective_id is not None:
        stmt = stmt.where(Decision.objective_id == objective_id)
    if task_id is not None:
        stmt = stmt.where(Decision.task_id == task_id)
    result = await db.execute(stmt)
    return [_decision_out(d) for d in result.scalars().all()]


@router.post("/{decision_id}/answer", response_model=None)
async def answer_decision(
    decision_id: int,
    body: DecisionAnswer,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    decision = await db.get(Decision, decision_id)
    if not decision:
        raise HTTPException(404, "Decision not found")
    decision.chosen_option = body.chosen_option
    decision.decision_state = DecisionState.answered
    decision.answered_by = user
    decision.answered_at = datetime.now(timezone.utc)
    await resume_orchestrator_from_decision(db, decision)
    await db.commit()
    await db.refresh(decision)
    await broadcast(
        {
            "type": "decision_answered",
            "decision_id": decision.id,
            "task_id": decision.task_id,
            "objective_id": decision.objective_id,
            "chosen_option": decision.chosen_option,
        }
    )
    return _decision_out(decision)
