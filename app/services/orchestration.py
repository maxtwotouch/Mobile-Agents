from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Decision,
    DecisionState,
    DecisionType,
    Message,
    MessageDirection,
    Objective,
    ObjectiveState,
    Priority,
    Role,
    Run,
    RunState,
    RunTriggerType,
    RuntimeState,
    RuntimeStatus,
    TargetType,
    Task,
    TaskKind,
    TaskStatus,
    ThreadState,
    Update,
    UpdateType,
    WorkflowState,
    default_target_type,
)
from app.services.adapters import adapter_for
from app.services.agent import AgentService
from app.services.roles import load_role_for_task, load_template
from app.services.state import (
    infer_run_trigger,
    mark_run_state,
    set_task_runtime_state,
    set_task_workflow_state,
    sync_task_thread,
)
from app.ws import broadcast

ORCHESTRATION_TAG = "orchestration"


def orchestration_prompt_contract() -> str:
    return f"""
You are acting as the orchestration agent for this objective.

Your job is to:
- clarify ambiguous requests by asking focused follow-up questions
- break work into child tasks when needed
- continue coordinating until the objective is complete
- return structured orchestration directives after every response

After your normal human-readable response, append a machine-readable block exactly like this:

<{ORCHESTRATION_TAG}>
{{
  "summary": "short summary of current orchestration state",
  "next_action_hint": "what should happen next",
  "questions": [
    {{
      "question": "Which branch should I target?",
      "options": ["main", "feature/x"],
      "recommended_option": "main",
      "decision_type": "branch_selection"
    }}
  ],
  "spawn_tasks": [
    {{
      "title": "Implement X",
      "description": "Concrete instructions for the child agent",
      "role": "developer",
      "task_kind": "implement",
      "target_type": "branch_diff",
      "target_branch": "feature/x",
      "base_branch": "main",
      "priority": "medium",
      "commit_start": null,
      "commit_end": null,
      "path_scope": null
    }}
  ]
}}
</{ORCHESTRATION_TAG}>

Rules:
- Always include the tag block, even if both arrays are empty.
- Only ask a question when you truly need user input.
- Only spawn tasks that are concrete and bounded.
- Do not spawn duplicate tasks for work already in progress.
""".strip()


def extract_directives(content: str) -> dict[str, Any] | None:
    pattern = re.compile(
        rf"<{ORCHESTRATION_TAG}>\s*(\{{.*?\}})\s*</{ORCHESTRATION_TAG}>",
        re.DOTALL,
    )
    matches = pattern.findall(content or "")
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def _clean_message_without_directives(content: str) -> str:
    return re.sub(
        rf"\s*<{ORCHESTRATION_TAG}>.*?</{ORCHESTRATION_TAG}>\s*",
        "",
        content or "",
        flags=re.DOTALL,
    ).strip()


async def _role_id_by_name(db: AsyncSession, name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    result = await db.execute(select(Role).where(Role.name == name))
    role = result.scalars().first()
    return role.id if role else None


def _normalize_task_kind(value: Optional[str]) -> TaskKind:
    try:
        return TaskKind(value or TaskKind.investigate.value)
    except ValueError:
        return TaskKind.investigate


def _normalize_target_type(
    value: Optional[str], target_branch: Optional[str], base_branch: Optional[str]
) -> TargetType:
    try:
        return TargetType(value or default_target_type(target_branch, base_branch).value)
    except ValueError:
        return default_target_type(target_branch, base_branch)


def _normalize_priority(value: Optional[str]) -> Priority:
    try:
        return Priority(value or Priority.medium.value)
    except ValueError:
        return Priority.medium


def _normalize_decision_type(value: Optional[str]) -> DecisionType:
    try:
        return DecisionType(value or DecisionType.clarification.value)
    except ValueError:
        return DecisionType.clarification


async def apply_orchestrator_response(
    db: AsyncSession,
    task: Task,
    response_text: str,
) -> str:
    if task.task_kind != TaskKind.orchestrate:
        return response_text

    cleaned = _clean_message_without_directives(response_text)
    directives = extract_directives(response_text) or {}

    if directives.get("summary"):
        task.result_summary = directives["summary"]
    if directives.get("next_action_hint"):
        task.next_action_hint = directives["next_action_hint"]

    for question in directives.get("questions", []):
        decision = Decision(
            objective_id=task.objective_id,
            task_id=task.id,
            decision_type=_normalize_decision_type(question.get("decision_type")),
            decision_state=DecisionState.open,
            question=question.get("question") or "Clarification needed",
            options=json.dumps(question.get("options") or []),
            recommended_option=question.get("recommended_option"),
        )
        db.add(decision)

    spawned = 0
    for child in directives.get("spawn_tasks", []):
        target_branch = child.get("target_branch")
        base_branch = child.get("base_branch")
        role_id = await _role_id_by_name(db, child.get("role"))
        child_task = Task(
            objective_id=task.objective_id,
            parent_task_id=task.id,
            title=child.get("title") or "Follow-up task",
            description=child.get("description") or "",
            repo_url=task.repo_url,
            branch=target_branch,
            base_branch=base_branch,
            agent_type=task.agent_type,
            role_id=role_id,
            task_kind=_normalize_task_kind(child.get("task_kind")),
            target_type=_normalize_target_type(
                child.get("target_type"), target_branch, base_branch
            ),
            priority=_normalize_priority(child.get("priority")),
            commit_start=child.get("commit_start"),
            commit_end=child.get("commit_end"),
            path_scope=child.get("path_scope"),
            status=TaskStatus.pending,
            workflow_status=TaskStatus.pending,
        )
        child_task.set_workflow_state(WorkflowState.ready)
        db.add(child_task)
        await db.flush()
        spawned += 1
        await broadcast(
            {"type": "task_created", "task_id": child_task.id, "title": child_task.title}
        )
        await dispatch_task_run(db, child_task, trigger_type=RunTriggerType.orchestrator_dispatch)

    if directives.get("questions"):
        set_task_workflow_state(task, WorkflowState.waiting_for_user, force=True)
    elif spawned:
        set_task_workflow_state(task, WorkflowState.blocked, force=True)
        task.blocked_reason = "Waiting on orchestrated child tasks"
    else:
        set_task_workflow_state(task, WorkflowState.waiting_for_user, force=True)
    return cleaned


async def summarize_child_result(db: AsyncSession, task: Task) -> str:
    stmt = (
        select(Message)
        .where(
            Message.task_id == task.id,
            Message.direction == MessageDirection.agent_to_user,
        )
        .order_by(Message.created_at.desc())
    )
    result = await db.execute(stmt)
    last_message = result.scalars().first()
    summary = task.result_summary or task.failure_reason or ""
    parts = [
        f"Child task #{task.id} finished.",
        f"Title: {task.title}",
        f"Kind: {task.task_kind.value}",
        f"Workflow state: {task.workflow_state.value}",
        f"Runtime state: {task.runtime_state.value}",
    ]
    if task.branch:
        parts.append(f"Branch: {task.branch}")
    if summary:
        parts.append(f"Summary: {summary}")
    if last_message and last_message.content:
        parts.append(f"Latest agent response:\n{last_message.content.strip()}")
    return "\n".join(parts)


async def has_open_decisions(db: AsyncSession, task: Task) -> bool:
    result = await db.execute(
        select(Decision).where(
            Decision.task_id == task.id,
            Decision.decision_state == DecisionState.open,
        )
    )
    return result.scalars().first() is not None


async def orchestrator_role_id(db: AsyncSession) -> Optional[int]:
    return await _role_id_by_name(db, "planner")


def build_objective_brief(objective: Objective) -> str:
    parts = [objective.title.strip()]
    if objective.description.strip():
        parts.append(objective.description.strip())
    return "\n\n".join(parts)


async def ensure_orchestrator_task(
    db: AsyncSession,
    objective: Objective,
    *,
    agent_type: str = "codex",
) -> Task:
    result = await db.execute(
        select(Task).where(
            Task.objective_id == objective.id,
            Task.task_kind == TaskKind.orchestrate,
        )
    )
    existing = result.scalars().first()
    if existing:
        return existing
    task = Task(
        objective_id=objective.id,
        title=f"Orchestrate: {objective.title}",
        description=build_objective_brief(objective),
        repo_url=objective.repo_url or "",
        agent_type=agent_type,
        role_id=await orchestrator_role_id(db),
        task_kind=TaskKind.orchestrate,
        target_type=TargetType.repo_head,
        priority=objective.priority,
        status=TaskStatus.pending,
        workflow_status=TaskStatus.pending,
    )
    task.set_workflow_state(WorkflowState.ready)
    task.set_runtime_state(RuntimeState.idle)
    db.add(task)
    await db.flush()
    await broadcast({"type": "task_created", "task_id": task.id, "title": task.title})
    return task


async def build_role_prompt(db: AsyncSession, task: Task) -> Optional[str]:
    role_prompt = None
    if task.role_id:
        role = await load_role_for_task(db, task.role_id)
        if role:
            role_prompt = load_template(role.template_path)
    if task.task_kind == TaskKind.orchestrate:
        orchestration = orchestration_prompt_contract()
        if role_prompt:
            role_prompt = f"{role_prompt}\n\n---\n\n{orchestration}"
        else:
            role_prompt = orchestration
    return role_prompt


async def dispatch_task_run(
    db: AsyncSession,
    task: Task,
    *,
    prompt: Optional[str] = None,
    trigger_type: Optional[RunTriggerType] = None,
) -> str:
    if task.runtime_status == RuntimeStatus.running:
        return task.runner_id or AgentService.runner_id(task)
    role_prompt = await build_role_prompt(db, task)
    set_task_runtime_state(task, RuntimeState.starting)
    set_task_workflow_state(task, WorkflowState.in_progress, force=True)
    runner_id = await adapter_for(task).start(task, prompt=prompt, role_prompt=role_prompt)
    task.runner_id = runner_id
    set_task_runtime_state(task, RuntimeState.running)
    task.last_run_started_at = datetime.now(timezone.utc)
    task.last_heartbeat_at = task.last_run_started_at
    await sync_task_thread(db, task, thread_state=ThreadState.active)
    run = Run(
        task_id=task.id,
        thread_id=task.thread_id,
        runner_id=runner_id,
        provider=task.agent_type,
        trigger_type=trigger_type or infer_run_trigger(task),
        status=RuntimeStatus.running,
        run_state=RunState.running,
        prompt=prompt,
        prompt_summary=prompt.strip()[:240] if prompt else None,
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
    await broadcast(
        {
            "type": "task_update",
            "task_id": task.id,
            "workflow_state": task.workflow_state.value,
            "runtime_state": task.runtime_state.value,
            "workflow_status": task.workflow_status.value,
            "runtime_status": task.runtime_status.value,
            "status": task.workflow_status.value,
        }
    )
    return runner_id


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
    result = await db.execute(
        select(Run)
        .where(Run.task_id == task.id, Run.runner_id == runner_id)
        .order_by(Run.started_at.desc())
    )
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


async def maybe_resume_parent_orchestrator(db: AsyncSession, task: Task) -> None:
    if not task.parent_task_id:
        return
    parent = await db.get(Task, task.parent_task_id)
    if not parent or parent.task_kind != TaskKind.orchestrate:
        return
    open_children = await db.execute(
        select(Task).where(
            Task.parent_task_id == parent.id,
            Task.workflow_state.in_(
                [
                    WorkflowState.ready,
                    WorkflowState.in_progress,
                    WorkflowState.blocked,
                    WorkflowState.waiting_for_user,
                    WorkflowState.needs_review,
                ]
            ),
            Task.id != task.id,
        )
    )
    if open_children.scalars().first():
        return
    if await has_open_decisions(db, parent):
        return
    summary = await summarize_child_result(db, task)
    db.add(
        Message(
            task_id=parent.id,
            direction=MessageDirection.user_to_agent,
            content=summary,
        )
    )
    parent.blocked_reason = None
    await dispatch_task_run(
        db,
        parent,
        prompt=summary,
        trigger_type=RunTriggerType.handoff,
    )


async def handle_task_completion(db: AsyncSession, task: Task, records: list[Any]) -> None:
    agent_messages = [
        r for r in records if isinstance(r, Message) and r.direction == MessageDirection.agent_to_user
    ]
    if task.task_kind == TaskKind.orchestrate and agent_messages:
        latest = agent_messages[-1]
        latest.content = await apply_orchestrator_response(db, task, latest.content)
    await maybe_resume_parent_orchestrator(db, task)


async def resume_orchestrator_from_decision(db: AsyncSession, decision: Decision) -> None:
    if not decision.task_id:
        return
    task = await db.get(Task, decision.task_id)
    if not task or task.task_kind != TaskKind.orchestrate:
        return
    if await has_open_decisions(db, task):
        return
    content = (
        f"Decision answered.\n\nQuestion: {decision.question}\n"
        f"Chosen option: {decision.chosen_option}"
    )
    db.add(
        Message(
            task_id=task.id,
            direction=MessageDirection.user_to_agent,
            content=content,
        )
    )
    await dispatch_task_run(
        db,
        task,
        prompt=content,
        trigger_type=RunTriggerType.message,
    )
