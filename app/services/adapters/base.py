from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from app.models import (
    Message,
    MessageDirection,
    RuntimeState,
    RuntimeStatus,
    Task,
    Update,
    UpdateType,
    WorkflowState,
)
from app.services.agent import AgentService
from app.services.state import set_task_runtime_state, set_task_workflow_state


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
        set_task_runtime_state(task, RuntimeState.stopped)
        set_task_workflow_state(task, WorkflowState.waiting_for_user, force=True)
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
        set_task_workflow_state(task, WorkflowState.needs_review, force=True)
        set_task_runtime_state(task, RuntimeState.idle)
        task.result_summary = "Agent run finished."
        task.failure_reason = None
        task.last_run_finished_at = datetime.now(timezone.utc)
        task.last_heartbeat_at = task.last_run_finished_at
        task.runner_id = None
        task.active_run_id = None
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
