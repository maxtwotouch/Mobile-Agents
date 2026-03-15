from app.models import Task
from app.services.adapters.base import BaseAgentAdapter
from app.services.adapters.claude import ClaudeAdapter
from app.services.adapters.codex import CodexAdapter


_ADAPTERS: dict[str, BaseAgentAdapter] = {
    "claude": ClaudeAdapter(),
    "codex": CodexAdapter(),
}


def adapter_for(task: Task) -> BaseAgentAdapter:
    return _ADAPTERS.get(task.agent_type, _ADAPTERS["claude"])
