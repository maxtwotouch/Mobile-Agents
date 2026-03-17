from typing import Optional

from app.models import Task, TaskStatus
from app.services.agent import AgentService
from app.services.adapters.base import BaseAgentAdapter


class ClaudeAdapter(BaseAgentAdapter):
    async def start(
        self, task: Task, prompt: Optional[str] = None, role_prompt: Optional[str] = None
    ) -> str:
        """Start or restart a Claude Code agent.

        First run: creates worktree, spawns interactive session, sends description.
        Restart: re-uses existing worktree, spawns fresh session, sends prompt.
        """
        is_restart = bool(task.worktree_path)

        if not is_restart:
            branch, worktree_path, base_branch = await AgentService.prepare_repo(task)
            task.branch = branch
            task.worktree_path = worktree_path
            task.base_branch = base_branch

        work_dir = task.worktree_path or task.repo_url
        effective_prompt = prompt or task.description

        if role_prompt:
            effective_prompt = f"{role_prompt}\n\n---\n\n## Your Task\n\n{effective_prompt}"

        return await AgentService.spawn(task, effective_prompt, work_dir=work_dir)

    async def send_message(self, task: Task, content: str) -> Optional[str]:
        if not task.tmux_session:
            raise RuntimeError("Agent is not currently running")
        await AgentService.send_message(task.tmux_session, content)
        return None

    def apply_post_run_state(self, task: Task) -> None:
        task.status = TaskStatus.needs_review
