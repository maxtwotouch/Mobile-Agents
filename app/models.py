import datetime
import enum
from typing import List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ObjectiveState(str, enum.Enum):
    draft = "draft"
    active = "active"
    waiting_for_user = "waiting_for_user"
    blocked = "blocked"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    paused = "paused"
    needs_review = "needs_review"
    completed = "completed"
    failed = "failed"


class WorkflowState(str, enum.Enum):
    draft = "draft"
    ready = "ready"
    in_progress = "in_progress"
    waiting_for_user = "waiting_for_user"
    blocked = "blocked"
    needs_review = "needs_review"
    approved = "approved"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class RuntimeStatus(str, enum.Enum):
    idle = "idle"
    running = "running"
    stopped = "stopped"
    failed = "failed"


class RuntimeState(str, enum.Enum):
    idle = "idle"
    queued = "queued"
    starting = "starting"
    running = "running"
    stopping = "stopping"
    stopped = "stopped"
    failed = "failed"


class TaskKind(str, enum.Enum):
    implement = "implement"
    review = "review"
    audit = "audit"
    investigate = "investigate"
    fix = "fix"
    refactor = "refactor"
    qa = "qa"
    release = "release"
    orchestrate = "orchestrate"


class TargetType(str, enum.Enum):
    repo_head = "repo_head"
    branch_diff = "branch_diff"
    commit_range = "commit_range"
    workspace_changes = "workspace_changes"
    file_scope = "file_scope"
    issue_followup = "issue_followup"


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ThreadState(str, enum.Enum):
    active = "active"
    idle = "idle"
    closed = "closed"
    failed = "failed"


class RunTriggerType(str, enum.Enum):
    manual_start = "manual_start"
    resume = "resume"
    message = "message"
    retry = "retry"
    handoff = "handoff"
    orchestrator_dispatch = "orchestrator_dispatch"


class RunState(str, enum.Enum):
    queued = "queued"
    starting = "starting"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    timed_out = "timed_out"


class DecisionType(str, enum.Enum):
    clarification = "clarification"
    approval = "approval"
    branch_selection = "branch_selection"
    next_action = "next_action"
    handoff = "handoff"
    retry_policy = "retry_policy"


class DecisionState(str, enum.Enum):
    open = "open"
    answered = "answered"
    expired = "expired"
    cancelled = "cancelled"


class UpdateType(str, enum.Enum):
    progress = "progress"
    commit = "commit"
    error = "error"
    summary = "summary"


class MessageDirection(str, enum.Enum):
    user_to_agent = "user_to_agent"
    agent_to_user = "agent_to_user"


def legacy_task_status_for_workflow(state: WorkflowState) -> TaskStatus:
    if state in {WorkflowState.ready, WorkflowState.in_progress, WorkflowState.draft}:
        return TaskStatus.pending
    if state in {
        WorkflowState.waiting_for_user,
        WorkflowState.blocked,
        WorkflowState.approved,
        WorkflowState.cancelled,
    }:
        return TaskStatus.paused
    if state == WorkflowState.needs_review:
        return TaskStatus.needs_review
    if state == WorkflowState.completed:
        return TaskStatus.completed
    return TaskStatus.failed


def legacy_runtime_status_for_runtime(state: RuntimeState) -> RuntimeStatus:
    if state in {RuntimeState.queued, RuntimeState.starting, RuntimeState.running}:
        return RuntimeStatus.running
    if state == RuntimeState.failed:
        return RuntimeStatus.failed
    if state == RuntimeState.stopped:
        return RuntimeStatus.stopped
    return RuntimeStatus.idle


def default_target_type(
    branch: Optional[str], base_branch: Optional[str]
) -> TargetType:
    if branch or base_branch:
        return TargetType.branch_diff
    return TargetType.repo_head


def infer_task_kind(agent_type: str, role_name: Optional[str]) -> TaskKind:
    if role_name == "reviewer":
        return TaskKind.review
    if role_name == "qa":
        return TaskKind.qa
    if role_name == "architect":
        return TaskKind.investigate
    if role_name == "release_engineer":
        return TaskKind.release
    if role_name == "planner":
        return TaskKind.orchestrate
    if agent_type == "codex":
        return TaskKind.implement
    return TaskKind.investigate


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    template_path: Mapped[str] = mapped_column(String(500))
    can_spawn: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class Objective(Base):
    __tablename__ = "objectives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    repo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority), default=Priority.medium
    )
    objective_state: Mapped[ObjectiveState] = mapped_column(
        Enum(ObjectiveState), default=ObjectiveState.draft
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_next_action: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    tasks: Mapped[List["Task"]] = relationship(back_populates="objective")
    decisions: Mapped[List["Decision"]] = relationship(back_populates="objective")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    objective_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("objectives.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    repo_url: Mapped[str] = mapped_column(String(500))
    branch: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    agent_type: Mapped[str] = mapped_column(String(50), default="claude")
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.pending
    )
    workflow_status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.pending
    )
    workflow_state: Mapped[WorkflowState] = mapped_column(
        Enum(WorkflowState), default=WorkflowState.ready
    )
    runtime_status: Mapped[RuntimeStatus] = mapped_column(
        Enum(RuntimeStatus), default=RuntimeStatus.idle
    )
    runtime_state: Mapped[RuntimeState] = mapped_column(
        Enum(RuntimeState), default=RuntimeState.idle
    )
    task_kind: Mapped[TaskKind] = mapped_column(
        Enum(TaskKind), default=TaskKind.investigate
    )
    target_type: Mapped[TargetType] = mapped_column(
        Enum(TargetType), default=TargetType.repo_head
    )
    commit_start: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    commit_end: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    path_scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority), default=Priority.medium
    )
    blocked_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_action_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thread_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    runner_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    codex_session_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    worktree_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    base_branch: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    last_run_started_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True
    )
    last_run_finished_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True
    )
    last_heartbeat_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True
    )
    role_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("roles.id"), nullable=True
    )
    parent_task_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tasks.id"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    objective: Mapped[Optional["Objective"]] = relationship(back_populates="tasks")
    role: Mapped[Optional["Role"]] = relationship()
    parent_task: Mapped[Optional["Task"]] = relationship(
        remote_side=[id], backref="child_tasks"
    )
    runs: Mapped[List["Run"]] = relationship(back_populates="task")
    updates: Mapped[List["Update"]] = relationship(back_populates="task")
    messages: Mapped[List["Message"]] = relationship(back_populates="task")
    thread: Mapped[Optional["Thread"]] = relationship(back_populates="task")
    decisions: Mapped[List["Decision"]] = relationship(back_populates="task")

    def set_workflow_state(self, state: WorkflowState) -> None:
        self.workflow_state = state
        legacy = legacy_task_status_for_workflow(state)
        self.workflow_status = legacy
        self.status = legacy

    def set_runtime_state(self, state: RuntimeState) -> None:
        self.runtime_state = state
        self.runtime_status = legacy_runtime_status_for_runtime(state)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    thread_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    runner_id: Mapped[str] = mapped_column(String(100))
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    trigger_type: Mapped[RunTriggerType] = mapped_column(
        Enum(RunTriggerType), default=RunTriggerType.manual_start
    )
    status: Mapped[RuntimeStatus] = mapped_column(Enum(RuntimeStatus))
    run_state: Mapped[RunState] = mapped_column(
        Enum(RunState), default=RunState.running
    )
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dispatch_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_output_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    finished_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True
    )

    task: Mapped["Task"] = relationship(back_populates="runs")


class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), unique=True)
    provider: Mapped[str] = mapped_column(String(50))
    provider_thread_id: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )
    thread_state: Mapped[ThreadState] = mapped_column(
        Enum(ThreadState), default=ThreadState.idle
    )
    context_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    task: Mapped["Task"] = relationship(back_populates="thread")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    objective_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("objectives.id"), nullable=True
    )
    task_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tasks.id"), nullable=True
    )
    decision_type: Mapped[DecisionType] = mapped_column(Enum(DecisionType))
    decision_state: Mapped[DecisionState] = mapped_column(
        Enum(DecisionState), default=DecisionState.open
    )
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_option: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chosen_option: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answered_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    answered_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    objective: Mapped[Optional["Objective"]] = relationship(back_populates="decisions")
    task: Mapped[Optional["Task"]] = relationship(back_populates="decisions")


class Update(Base):
    __tablename__ = "updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    type: Mapped[UpdateType] = mapped_column(Enum(UpdateType))
    content: Mapped[str] = mapped_column(Text)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    branch: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    task: Mapped["Task"] = relationship(back_populates="updates")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    direction: Mapped[MessageDirection] = mapped_column(Enum(MessageDirection))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    task: Mapped["Task"] = relationship(back_populates="messages")
