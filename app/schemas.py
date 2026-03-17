import datetime
from typing import Optional

from pydantic import BaseModel

from app.models import MessageDirection, RuntimeStatus, TaskStatus, UpdateType


# --- Roles ---


class RoleOut(BaseModel):
    id: int
    name: str
    description: str
    can_spawn: Optional[list[str]] = None

    model_config = {"from_attributes": True}


# --- Tasks ---


class TaskCreate(BaseModel):
    title: str
    description: str
    repo_url: str
    branch: Optional[str] = None
    base_branch: Optional[str] = None
    agent_type: str = "claude"
    role_id: Optional[int] = None


class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    repo_url: str
    branch: Optional[str]
    base_branch: Optional[str]
    agent_type: str
    workflow_status: TaskStatus
    runtime_status: RuntimeStatus
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
    workflow_status: Optional[TaskStatus] = None
    runtime_status: Optional[RuntimeStatus] = None
    branch: Optional[str] = None
    base_branch: Optional[str] = None


class RunOut(BaseModel):
    id: int
    task_id: int
    thread_id: Optional[str]
    runner_id: str
    status: RuntimeStatus
    prompt: Optional[str]
    exit_code: Optional[int]
    error: Optional[str]
    started_at: datetime.datetime
    finished_at: Optional[datetime.datetime]

    model_config = {"from_attributes": True}


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
