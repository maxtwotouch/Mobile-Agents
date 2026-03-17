from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from app.models import (
    Message,
    MessageDirection,
    RuntimeStatus,
    Task,
    TaskStatus,
    Update,
    UpdateType,
)
from app.services.agent import AgentService


class BaseAgentAdapter(ABC):
    @abstractmethod
    async def start(
        self, task: Task, prompt: Optional[str] = None, role_prompt: Optional[str] = None
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def send_message(self, task: Task, content: str) -> Optional[str]:
        raise NotImplementedError

    async def stop(self, task: Task) -> None:
        runner_id = task.runner_id or AgentService.runner_id(task)
        await AgentService.kill(runner_id)
        task.runner_id = None
        task.runtime_status = RuntimeStatus.stopped
        task.workflow_status = TaskStatus.paused
        task.status = TaskStatus.paused
        task.last_run_finished_at = datetime.now(timezone.utc)

    async def is_alive(self, task: Task) -> bool:
        runner_id = task.runner_id or AgentService.runner_id(task)
        return await AgentService.is_alive(runner_id)

    async def capture_output(self, task: Task, lines: int = 50) -> str:
        runner_id = task.runner_id or AgentService.runner_id(task)
        return await AgentService.capture_output(runner_id, lines)

    def finalize_records(self, task: Task, output: str) -> list[Update | Message]:
        records: list[Update | Message] = [
            Update(
                task_id=task.id,
                type=UpdateType.summary,
                content="Agent run finished.",
            )
        ]
        task.workflow_status = TaskStatus.needs_review
        task.status = TaskStatus.needs_review
        task.runtime_status = RuntimeStatus.idle
        task.last_run_finished_at = datetime.now(timezone.utc)
        task.last_heartbeat_at = task.last_run_finished_at
        task.runner_id = None
        return records

    def apply_post_run_state(self, task: Task) -> None:
        pass

    def _append_agent_reply(
        self, records: list[Update | Message], task: Task, content: str
    ) -> None:
        if not content:
            return
        records.append(
            Message(
                task_id=task.id,
                direction=MessageDirection.agent_to_user,
                content=content,
            )
        )
