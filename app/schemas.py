import datetime
from typing import Optional

from pydantic import BaseModel

from app.models import (
    DecisionState,
    DecisionType,
    MessageDirection,
    ObjectiveState,
    Priority,
    RunState,
    RunTriggerType,
    RuntimeState,
    RuntimeStatus,
    TargetType,
    TaskKind,
    TaskStatus,
    UpdateType,
    WorkflowState,
)


# --- Roles ---


class RoleOut(BaseModel):
    id: int
    name: str
    description: str
    can_spawn: Optional[list[str]] = None

    model_config = {"from_attributes": True}


# --- Tasks ---


class ObjectiveCreate(BaseModel):
    title: str
    description: str = ""
    repo_url: Optional[str] = None
    priority: Priority = Priority.medium
    agent_type: str = "codex"


class ObjectivePatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    repo_url: Optional[str] = None
    priority: Optional[Priority] = None
    objective_state: Optional[ObjectiveState] = None
    summary: Optional[str] = None
    recommended_next_action: Optional[str] = None


class ObjectiveOut(BaseModel):
    id: int
    title: str
    description: str
    repo_url: Optional[str]
    created_by: Optional[str]
    priority: Priority
    objective_state: ObjectiveState
    summary: Optional[str]
    recommended_next_action: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str
    description: str
    repo_url: str
    branch: Optional[str] = None
    base_branch: Optional[str] = None
    agent_type: str = "claude"
    role_id: Optional[int] = None
    objective_id: Optional[int] = None
    task_kind: Optional[TaskKind] = None
    target_type: Optional[TargetType] = None
    priority: Priority = Priority.medium
    commit_start: Optional[str] = None
    commit_end: Optional[str] = None
    path_scope: Optional[str] = None


class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    repo_url: str
    branch: Optional[str]
    base_branch: Optional[str]
    agent_type: str
    objective_id: Optional[int]
    task_kind: TaskKind
    target_type: TargetType
    priority: Priority
    workflow_state: WorkflowState
    workflow_status: TaskStatus
    runtime_state: RuntimeState
    runtime_status: RuntimeStatus
    commit_start: Optional[str]
    commit_end: Optional[str]
    path_scope: Optional[str]
    active_run_id: Optional[int]
    blocked_reason: Optional[str]
    result_summary: Optional[str]
    failure_reason: Optional[str]
    next_action_hint: Optional[str]
    thread_id: Optional[str]
    runner_id: Optional[str]
    codex_session_id: Optional[str]
    worktree_path: Optional[str]
    last_run_started_at: Optional[datetime.datetime]
    last_run_finished_at: Optional[datetime.datetime]
    last_heartbeat_at: Optional[datetime.datetime]
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    parent_task_id: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class TaskPatch(BaseModel):
    task_kind: Optional[TaskKind] = None
    target_type: Optional[TargetType] = None
    priority: Optional[Priority] = None
    workflow_state: Optional[WorkflowState] = None
    workflow_status: Optional[TaskStatus] = None
    runtime_state: Optional[RuntimeState] = None
    runtime_status: Optional[RuntimeStatus] = None
    branch: Optional[str] = None
    base_branch: Optional[str] = None
    commit_start: Optional[str] = None
    commit_end: Optional[str] = None
    path_scope: Optional[str] = None
    blocked_reason: Optional[str] = None
    result_summary: Optional[str] = None
    failure_reason: Optional[str] = None
    next_action_hint: Optional[str] = None


class RunOut(BaseModel):
    id: int
    task_id: int
    thread_id: Optional[str]
    runner_id: str
    provider: Optional[str]
    trigger_type: RunTriggerType
    run_state: RunState
    status: RuntimeStatus
    prompt: Optional[str]
    dispatch_snapshot: Optional[str]
    prompt_summary: Optional[str]
    exit_code: Optional[int]
    error_type: Optional[str]
    error: Optional[str]
    output_summary: Optional[str]
    raw_output_ref: Optional[str]
    started_at: datetime.datetime
    finished_at: Optional[datetime.datetime]

    model_config = {"from_attributes": True}


class DecisionCreate(BaseModel):
    objective_id: Optional[int] = None
    task_id: Optional[int] = None
    decision_type: DecisionType
    question: str
    options: Optional[list[str]] = None
    recommended_option: Optional[str] = None


class DecisionAnswer(BaseModel):
    chosen_option: str


class DecisionOut(BaseModel):
    id: int
    objective_id: Optional[int]
    task_id: Optional[int]
    decision_type: DecisionType
    decision_state: DecisionState
    question: str
    options: Optional[list[str]]
    recommended_option: Optional[str]
    chosen_option: Optional[str]
    answered_by: Optional[str]
    answered_at: Optional[datetime.datetime]
    created_at: datetime.datetime


# --- Updates ---


class UpdateCreate(BaseModel):
    type: UpdateType
    content: str
    commit_sha: Optional[str] = None
    branch: Optional[str] = None


class UpdateOut(BaseModel):
    id: int
    task_id: int
    type: UpdateType
    content: str
    commit_sha: Optional[str]
    branch: Optional[str]
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# --- Messages ---


class MessageCreate(BaseModel):
    content: str
    direction: MessageDirection = MessageDirection.user_to_agent


class MessageOut(BaseModel):
    id: int
    task_id: int
    direction: MessageDirection
    content: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
