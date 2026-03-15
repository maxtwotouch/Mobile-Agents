from typing import Optional

from app.models import Task, TaskStatus
from app.services.agent import AgentService
from app.services.adapters.base import BaseAgentAdapter


class ClaudeAdapter(BaseAgentAdapter):
    async def start(self, task: Task) -> str:
        task.branch = await AgentService.prepare_repo(task)
        return await AgentService.spawn(task, task.description)

    async def send_message(self, task: Task, content: str) -> Optional[str]:
        if not task.tmux_session:
            raise RuntimeError("Agent is not currently running")
        await AgentService.send_message(task.tmux_session, content)
        return None

    def apply_post_run_state(self, task: Task) -> None:
        task.status = TaskStatus.needs_review
