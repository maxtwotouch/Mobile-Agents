from typing import Optional

from app.models import RuntimeStatus, Task
from app.services.agent import AgentService
from app.services.adapters.base import BaseAgentAdapter


class ClaudeAdapter(BaseAgentAdapter):
    def _build_prompt(
        self, task: Task, prompt: Optional[str], role_prompt: Optional[str]
    ) -> str:
        thread_id = AgentService.ensure_thread_id(task)
        sections: list[str] = []

        if role_prompt:
            sections.append(role_prompt.strip())

        if task.description.strip():
            sections.append(f"## Task\n\n{task.description.strip()}")

        transcript = AgentService.read_transcript(thread_id)
        if transcript:
            sections.append(f"## Conversation So Far\n\n{transcript}")

        if prompt and prompt.strip():
            sections.append(f"## New User Message\n\n{prompt.strip()}")

        return "\n\n---\n\n".join(part for part in sections if part).strip()

    async def start(
        self, task: Task, prompt: Optional[str] = None, role_prompt: Optional[str] = None
    ) -> str:
        is_restart = bool(task.worktree_path)

        if not is_restart:
            branch, worktree_path, base_branch = await AgentService.prepare_repo(task)
            task.branch = branch
            task.worktree_path = worktree_path
            task.base_branch = base_branch

        AgentService.ensure_thread_id(task)
        work_dir = task.worktree_path or task.repo_url
        if role_prompt and not AgentService.read_transcript(task.thread_id):
            AgentService.append_transcript(task.thread_id, "Role", role_prompt)
        effective_prompt = self._build_prompt(task, prompt, role_prompt)
        return await AgentService.spawn(task, effective_prompt, work_dir=work_dir)

    async def send_message(self, task: Task, content: str) -> Optional[str]:
        if not task.worktree_path:
            raise RuntimeError("No Claude thread exists yet — start the task first")

        task.runner_id = await self.start(task, prompt=content)
        task.runtime_status = RuntimeStatus.running
        AgentService.append_transcript(task.thread_id, "User", content)
        return task.runner_id

    def finalize_records(self, task: Task, output: str):
        records = super().finalize_records(task, output)
        reply = AgentService.read_last_message(AgentService.runner_id(task))
        AgentService.append_transcript(task.thread_id, "Agent", reply)
        self._append_agent_reply(records, task, reply)
        return records
