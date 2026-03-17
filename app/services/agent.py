import asyncio
import json
import logging
import os
import re
import shlex
import shutil
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("agent")

_processes: Dict[str, asyncio.subprocess.Process] = {}
_output_buffers: Dict[str, list[str]] = {}
_reader_tasks: Dict[str, asyncio.Task] = {}
_exit_codes: Dict[str, int] = {}

OUTPUT_BUFFER_LINES = 200
RUNTIME_DIR = Path(os.environ.get("MA_RUNTIME_DIR", "/tmp/mobile_agents"))
LOG_DIR = RUNTIME_DIR / "logs"
MESSAGE_DIR = RUNTIME_DIR / "messages"
PROMPT_DIR = RUNTIME_DIR / "prompts"
TRANSCRIPT_DIR = RUNTIME_DIR / "transcripts"


def _agent_binary(task) -> str:
    return "codex" if task.agent_type == "codex" else "claude"


def _ensure_repo_path(repo_path: str) -> None:
    if not repo_path:
        raise RuntimeError("Task is missing a repository path")
    if not os.path.isdir(repo_path):
        raise RuntimeError(f"Repository path does not exist: {repo_path}")


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _log_path(runner_id: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR / f"{_safe_name(runner_id)}.log"


def _message_path(runner_id: str) -> Path:
    MESSAGE_DIR.mkdir(parents=True, exist_ok=True)
    return MESSAGE_DIR / f"{_safe_name(runner_id)}.txt"


def _prompt_path(runner_id: str) -> Path:
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    return PROMPT_DIR / f"{_safe_name(runner_id)}.txt"


def _transcript_path(thread_id: str) -> Path:
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    return TRANSCRIPT_DIR / f"{_safe_name(thread_id)}.md"


def _tail_lines(path: Path, lines: int) -> str:
    if not path.exists():
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return "".join(handle.readlines()[-lines:]).rstrip()


async def _run_git(repo_path: str, *args: str) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        repo_path,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return (
        proc.returncode,
        stdout.decode(errors="replace").strip(),
        stderr.decode(errors="replace").strip(),
    )


async def _read_output(
    runner_id: str, proc: asyncio.subprocess.Process, log_path: Path
) -> None:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log_file:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                decoded = line.decode(errors="replace").rstrip("\n")
                log_file.write(decoded + "\n")
                log_file.flush()
                buf = _output_buffers.get(runner_id)
                if buf is not None:
                    buf.append(decoded)
                    if len(buf) > OUTPUT_BUFFER_LINES:
                        del buf[: len(buf) - OUTPUT_BUFFER_LINES]
        await proc.wait()
    except Exception:
        logger.exception("Error reading output for %s", runner_id)
    finally:
        if proc.returncode is not None:
            _exit_codes[runner_id] = proc.returncode
        _processes.pop(runner_id, None)
        _reader_tasks.pop(runner_id, None)


class AgentService:
    """Manages agent runs as background subprocesses with durable thread IDs."""

    @staticmethod
    def is_codex(task) -> bool:
        return _agent_binary(task) == "codex"

    @staticmethod
    def default_branch_name(task) -> str:
        return f"agent/task-{task.id}"

    @staticmethod
    def default_thread_id(task) -> str:
        return f"{task.agent_type}-task-{task.id}"

    @staticmethod
    def ensure_thread_id(task) -> str:
        if not task.thread_id:
            task.thread_id = task.codex_session_id or AgentService.default_thread_id(task)
        return task.thread_id

    @staticmethod
    def runner_id(task) -> str:
        return task.runner_id or f"task-{task.id}"

    @staticmethod
    def default_resume_prompt(task) -> str:
        return (
            "Continue the task from the existing thread context. "
            "Inspect the current repository state and proceed."
        )

    @staticmethod
    async def prepare_repo(task) -> tuple[str, str, str]:
        """Validate repo, create worktree, return (branch, worktree_path, base_branch)."""
        from app.services.repo import _detect_default_branch, create_worktree

        repo_path = task.repo_url
        _ensure_repo_path(repo_path)

        code, stdout, stderr = await _run_git(
            repo_path, "rev-parse", "--is-inside-work-tree"
        )
        if code != 0 or stdout != "true":
            raise RuntimeError(
                f"Repository path is not a git repository: {stderr or repo_path}"
            )

        branch = task.branch or AgentService.default_branch_name(task)
        base_branch = task.base_branch or await _detect_default_branch(repo_path)
        worktree_path = await create_worktree(repo_path, branch, task.id)
        return branch, worktree_path, base_branch

    @staticmethod
    async def spawn(task, prompt: Optional[str] = None, work_dir: Optional[str] = None) -> str:
        """Spawn a background agent run for the task."""
        runner_id = AgentService.runner_id(task)
        cwd = work_dir or task.worktree_path or task.repo_url
        _ensure_repo_path(cwd)

        agent_binary = _agent_binary(task)
        if shutil.which(agent_binary) is None:
            raise FileNotFoundError(f"Agent CLI '{agent_binary}' not found")

        log_path = _log_path(runner_id)
        message_path = _message_path(runner_id)
        prompt_path = _prompt_path(runner_id)
        log_path.write_text("", encoding="utf-8")
        message_path.write_text("", encoding="utf-8")

        if AgentService.is_codex(task):
            if task.thread_id or task.codex_session_id:
                thread_id = task.thread_id or task.codex_session_id
                resume_prompt = (prompt or "").strip() or AgentService.default_resume_prompt(task)
                agent_cmd = (
                    f"codex exec resume --dangerously-bypass-approvals-and-sandbox "
                    f"--skip-git-repo-check --json "
                    f"-o {shlex.quote(str(message_path))} "
                    f"{shlex.quote(thread_id)} "
                    f"{shlex.quote(resume_prompt)}"
                )
            else:
                effective_prompt = (prompt or task.description or "").strip()
                if not effective_prompt:
                    raise RuntimeError("Codex task is missing a prompt")
                agent_cmd = (
                    f"codex exec --dangerously-bypass-approvals-and-sandbox "
                    f"--skip-git-repo-check --json "
                    f"-o {shlex.quote(str(message_path))} "
                    f"{shlex.quote(effective_prompt)}"
                )
        else:
            effective_prompt = (prompt or task.description or "").strip()
            if not effective_prompt:
                raise RuntimeError("Claude task is missing a prompt")
            prompt_path.write_text(effective_prompt, encoding="utf-8")
            agent_cmd = (
                f"cat {shlex.quote(str(prompt_path))} | "
                f"claude -p --dangerously-skip-permissions "
                f"--add-dir {shlex.quote(cwd)}"
            )

        await AgentService.kill(runner_id)

        proc = await asyncio.create_subprocess_shell(
            f"{agent_cmd} 2>&1",
            cwd=cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        _processes[runner_id] = proc
        _output_buffers[runner_id] = []
        _reader_tasks[runner_id] = asyncio.create_task(
            _read_output(runner_id, proc, log_path)
        )
        return runner_id

    @staticmethod
    async def kill(runner_id: str) -> None:
        proc = _processes.pop(runner_id, None)
        reader = _reader_tasks.pop(runner_id, None)
        if proc and proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        if reader:
            reader.cancel()
        _output_buffers.pop(runner_id, None)

    @staticmethod
    async def is_alive(runner_id: str) -> bool:
        proc = _processes.get(runner_id)
        if proc is None:
            return False
        if proc.returncode is not None:
            _exit_codes[runner_id] = proc.returncode
            _processes.pop(runner_id, None)
            return False
        return True

    @staticmethod
    async def capture_output(runner_id: str, lines: int = 50) -> str:
        log_output = _tail_lines(_log_path(runner_id), lines)
        if log_output:
            return log_output
        buf = _output_buffers.get(runner_id, [])
        return "\n".join(buf[-lines:])

    @staticmethod
    def extract_codex_session_id(runner_id: str) -> Optional[str]:
        log_path = _log_path(runner_id)
        if not log_path.exists():
            return None
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "thread.started":
                    return event.get("thread_id")
        return None

    @staticmethod
    def read_last_message(runner_id: str) -> str:
        path = _message_path(runner_id)
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace").strip()
        return _tail_lines(_log_path(runner_id), 200).strip()

    @staticmethod
    def read_transcript(thread_id: Optional[str]) -> str:
        if not thread_id:
            return ""
        path = _transcript_path(thread_id)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace").strip()

    @staticmethod
    def append_transcript(thread_id: Optional[str], speaker: str, content: str) -> None:
        if not thread_id or not content.strip():
            return
        path = _transcript_path(thread_id)
        existing = ""
        if path.exists():
            existing = path.read_text(encoding="utf-8", errors="replace").rstrip()
        block = f"## {speaker}\n\n{content.strip()}"
        text = f"{existing}\n\n{block}".strip() if existing else block
        path.write_text(text + "\n", encoding="utf-8")

    @staticmethod
    def consume_exit_code(runner_id: str) -> Optional[int]:
        return _exit_codes.pop(runner_id, None)
