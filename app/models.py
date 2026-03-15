import datetime
import enum
from typing import List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    paused = "paused"
    needs_review = "needs_review"
    completed = "completed"
    failed = "failed"


class UpdateType(str, enum.Enum):
    progress = "progress"
    commit = "commit"
    error = "error"
    summary = "summary"


class MessageDirection(str, enum.Enum):
    user_to_agent = "user_to_agent"
    agent_to_user = "agent_to_user"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    repo_url: Mapped[str] = mapped_column(String(500))
    branch: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    agent_type: Mapped[str] = mapped_column(String(50), default="claude")
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.pending
    )
    tmux_session: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    codex_session_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    updates: Mapped[List["Update"]] = relationship(back_populates="task")
    messages: Mapped[List["Message"]] = relationship(back_populates="task")


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
