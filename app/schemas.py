import datetime
from typing import Optional

from pydantic import BaseModel

from app.models import MessageDirection, TaskStatus, UpdateType


# --- Tasks ---


class TaskCreate(BaseModel):
    title: str
    description: str
    repo_url: str
    branch: Optional[str] = None
    base_branch: Optional[str] = None
    agent_type: str = "claude"


class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    repo_url: str
    branch: Optional[str]
    base_branch: Optional[str]
    agent_type: str
    status: TaskStatus
    tmux_session: Optional[str]
    codex_session_id: Optional[str]
    worktree_path: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class TaskPatch(BaseModel):
    status: Optional[TaskStatus] = None
    branch: Optional[str] = None
    base_branch: Optional[str] = None


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
