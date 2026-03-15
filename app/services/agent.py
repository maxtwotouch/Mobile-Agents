import asyncio
import json
import logging
import os
import shlex
import shutil
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("agent")

# Track background processes when tmux is not available
_processes: Dict[str, asyncio.subprocess.Process] = {}
_output_buffers: Dict[str, list] = {}

OUTPUT_BUFFER_LINES = 200
STARTUP_GRACE_SECONDS = 1.0
RUNTIME_DIR = Path(os.environ.get("MA_RUNTIME_DIR", "/tmp/mobile_agents"))
LOG_DIR = RUNTIME_DIR / "logs"
MESSAGE_DIR = RUNTIME_DIR / "messages"


def _has_tmux() -> bool:
    return shutil.which("tmux") is not None


def _shell() -> str:
    return os.environ.get("SHELL") or "/bin/sh"


def _agent_binary(task) -> str:
    return "codex" if task.agent_type == "codex" else "claude"


def _agent_command(task) -> str:
    binary = _agent_binary(task)
    if binary == "codex":
        return f"{binary} --dangerously-bypass-approvals-and-sandbox --no-alt-screen"
    return f"{binary} --dangerously-skip-permissions"


def _ensure_repo_path(repo_path: str) -> None:
    if not repo_path:
        raise RuntimeError("Task is missing a repository path")
    if not os.path.isdir(repo_path):
        raise RuntimeError(f"Repository path does not exist: {repo_path}")


def _log_path(session_name: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR / f"{session_name}.log"


def _message_path(session_name: str) -> Path:
    MESSAGE_DIR.mkdir(parents=True, exist_ok=True)
    return MESSAGE_DIR / f"{session_name}.txt"


def _tail_lines(path: Path, lines: int) -> str:
    if not path.exists():
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return "".join(handle.readlines()[-lines:]).rstrip()


async def _run_git(repo_path: str, *args: str) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        "git", "-C", repo_path, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return (
        proc.returncode,
        stdout.decode(errors="replace").strip(),
        stderr.decode(errors="replace").strip(),
    )


class AgentService:
    """Manages agent processes via tmux (preferred) or subprocess fallback."""

    @staticmethod
    def is_codex(task) -> bool:
        return _agent_binary(task) == "codex"

    @staticmethod
    def default_branch_name(task) -> str:
        return f"agent/task-{task.id}"

    @staticmethod
    async def prepare_repo(task) -> tuple[str, str, str]:
        """Validate repo, create worktree, return (branch, worktree_path, base_branch).

        Uses git worktrees so each task gets an isolated working copy.
        """
        from app.services.repo import create_worktree, _detect_default_branch

        repo_path = task.repo_url
        _ensure_repo_path(repo_path)

        code, stdout, stderr = await _run_git(repo_path, "rev-parse", "--is-inside-work-tree")
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
        """Spawn an agent run. Uses worktree_path as working directory if provided."""
        session_name = f"agent-{task.id}"
        cwd = work_dir or task.worktree_path or task.repo_url
        _ensure_repo_path(cwd)

        agent_binary = _agent_binary(task)
        if shutil.which(agent_binary) is None:
            raise FileNotFoundError(f"Agent CLI '{agent_binary}' not found")
        if not _has_tmux():
            raise RuntimeError("tmux is required for persistent interactive agent sessions")

        log_path = _log_path(session_name)
        message_path = _message_path(session_name)
        log_path.write_text("", encoding="utf-8")
        message_path.write_text("", encoding="utf-8")

        if AgentService.is_codex(task):
            is_resume = bool(task.codex_session_id)

            if is_resume:
                # Resume existing session — prompt is optional
                agent_cmd = (
                    f"codex exec resume --dangerously-bypass-approvals-and-sandbox "
                    f"--skip-git-repo-check --json "
                    f"-o {shlex.quote(str(message_path))} "
                    f"{shlex.quote(task.codex_session_id)}"
                )
                if prompt and prompt.strip():
                    agent_cmd += f" {shlex.quote(prompt.strip())}"
            else:
                # First run — prompt is required
                effective_prompt = (prompt or task.description or "").strip()
                if not effective_prompt:
                    raise RuntimeError("Codex task is missing a prompt")
                agent_cmd = (
                    f"codex exec --dangerously-bypass-approvals-and-sandbox "
                    f"--skip-git-repo-check --json "
                    f"-o {shlex.quote(str(message_path))} "
                    f"{shlex.quote(effective_prompt)}"
                )
            shell_cmd = f"{agent_cmd} 2>&1 | tee -a {shlex.quote(str(log_path))}"
        else:
            agent_cmd = _agent_command(task)
            shell_cmd = f"exec {agent_cmd}"

        try:
            await AgentService.kill(session_name)
        except Exception:
            pass

        proc = await asyncio.create_subprocess_exec(
            "tmux", "new-session", "-d",
            "-s", session_name,
            "-c", cwd,
            _shell(), "-lc", shell_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to spawn tmux session: {stderr.decode()}")

        await asyncio.sleep(STARTUP_GRACE_SECONDS)
        if not await AgentService.is_alive(session_name):
            last_output = await AgentService.capture_output(session_name)
            raise RuntimeError(
                "Agent exited immediately."
                + (f" Last output:\n{last_output}" if last_output else "")
            )

        if not AgentService.is_codex(task) and task.description.strip():
            await AgentService.send_message(session_name, task.description)

        return session_name

    @staticmethod
    async def kill(session_name: str) -> None:
        if _has_tmux():
            proc = await asyncio.create_subprocess_shell(
                f"tmux kill-session -t {session_name}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        else:
            proc = _processes.pop(session_name, None)
            if proc and proc.returncode is None:
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()
            _output_buffers.pop(session_name, None)

    @staticmethod
    async def is_alive(session_name: str) -> bool:
        if _has_tmux():
            proc = await asyncio.create_subprocess_shell(
                f"tmux has-session -t {session_name}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        else:
            proc = _processes.get(session_name)
            return proc is not None and proc.returncode is None

    @staticmethod
    async def capture_output(session_name: str, lines: int = 50) -> str:
        if _has_tmux():
            proc = await asyncio.create_subprocess_exec(
                "tmux", "capture-pane", "-t", session_name,
                "-p", "-S", f"-{lines}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                output = stdout.decode()
                _log_path(session_name).write_text(output, encoding="utf-8")
                return output

        log_output = _tail_lines(_log_path(session_name), lines)
        if log_output:
            return log_output

        buf = _output_buffers.get(session_name, [])
        return "\n".join(buf[-lines:])

    @staticmethod
    def extract_codex_session_id(session_name: str) -> Optional[str]:
        log_path = _log_path(session_name)
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
    def read_last_message(session_name: str) -> str:
        path = _message_path(session_name)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace").strip()

    @staticmethod
    async def send_message(session_name: str, content: str) -> None:
        if not content.strip():
            return
        if not _has_tmux():
            raise RuntimeError("tmux is required for interactive agent messaging")
        if not await AgentService.is_alive(session_name):
            raise RuntimeError("Agent session is not running")

        proc = await asyncio.create_subprocess_exec(
            "tmux", "send-keys", "-t", session_name,
            content, "Enter",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to send message to agent: {stderr.decode().strip()}")


async def _read_output(
    session_name: str, proc: asyncio.subprocess.Process, log_path: Path
):
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
                buf = _output_buffers.get(session_name)
                if buf is not None:
                    buf.append(decoded)
                    if len(buf) > OUTPUT_BUFFER_LINES:
                        del buf[: len(buf) - OUTPUT_BUFFER_LINES]
    except Exception:
        logger.exception("Error reading output for %s", session_name)
    finally:
        _processes.pop(session_name, None)
