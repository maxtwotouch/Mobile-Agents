from typing import Optional

from app.models import Task, TaskStatus
from app.services.agent import AgentService
from app.services.adapters.base import BaseAgentAdapter


class CodexAdapter(BaseAgentAdapter):
    async def start(self, task: Task) -> str:
        task.branch = await AgentService.prepare_repo(task)
        return await AgentService.spawn(task, task.description)

    async def send_message(self, task: Task, content: str) -> Optional[str]:
        if task.status == TaskStatus.running:
            raise RuntimeError("Codex is already handling a prompt")
        if not task.codex_session_id:
            raise RuntimeError("Codex session has not been initialized yet")
        task.branch = await AgentService.prepare_repo(task)
        task.tmux_session = await AgentService.spawn(task, content)
        task.status = TaskStatus.running
        return task.tmux_session

    def finalize_records(self, task: Task, output: str):
        records = super().finalize_records(task, output)
        session_name = f"agent-{task.id}"
        session_id = AgentService.extract_codex_session_id(session_name)
        if session_id:
            task.codex_session_id = session_id
        self._append_agent_reply(
            records,
            task,
            AgentService.read_last_message(session_name),
        )
        return records

    def apply_post_run_state(self, task: Task) -> None:
        task.status = TaskStatus.needs_review
