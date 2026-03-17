from typing import Optional

from app.models import Task, TaskStatus
from app.services.agent import AgentService
from app.services.adapters.base import BaseAgentAdapter


class CodexAdapter(BaseAgentAdapter):
    async def start(
        self, task: Task, prompt: Optional[str] = None, role_prompt: Optional[str] = None
    ) -> str:
        """Start or resume a Codex agent.

        First run: creates worktree, runs `codex exec` with task.description.
        Resume: re-uses existing worktree/session, runs `codex exec resume`
        with the provided prompt (or no new prompt if None).
        """
        is_resume = bool(task.codex_session_id)

        if not is_resume:
            # First run — set up worktree
            branch, worktree_path, base_branch = await AgentService.prepare_repo(task)
            task.branch = branch
            task.worktree_path = worktree_path
            task.base_branch = base_branch

        work_dir = task.worktree_path or task.repo_url
        effective_prompt = prompt or (task.description if not is_resume else None)

        if role_prompt and effective_prompt:
            effective_prompt = f"{role_prompt}\n\n---\n\n## Your Task\n\n{effective_prompt}"

        return await AgentService.spawn(task, effective_prompt, work_dir=work_dir)

    async def send_message(self, task: Task, content: str) -> Optional[str]:
        """Send a follow-up to Codex by resuming the session with a new prompt."""
        if task.status == TaskStatus.running:
            raise RuntimeError("Codex is already handling a prompt — wait for it to finish")
        if not task.codex_session_id:
            raise RuntimeError("No Codex session to resume — start the task first")

        task.tmux_session = await self.start(task, prompt=content)
        task.status = TaskStatus.running
        return task.tmux_session

    def finalize_records(self, task: Task, output: str):
        records = super().finalize_records(task, output)
        session_name = f"agent-{task.id}"
        session_id = AgentService.extract_codex_session_id(session_name)
        if session_id:
            task.codex_session_id = session_id
        self._append_agent_reply(
            records, task, AgentService.read_last_message(session_name),
        )
        return records

    def apply_post_run_state(self, task: Task) -> None:
        task.status = TaskStatus.needs_review
