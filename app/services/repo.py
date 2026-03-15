"""Repository management: clone, list, and resolve repos in the workspace."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("repo")

WORKSPACE_DIR = Path(os.environ.get("MA_WORKSPACE", os.path.expanduser("~/agent-repos")))


def _ensure_workspace() -> Path:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    return WORKSPACE_DIR


async def _git(cwd: str, *args: str) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        "git", "-C", cwd, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(errors="replace").strip(), stderr.decode(errors="replace").strip()


async def clone_repo(url: str, name: Optional[str] = None) -> dict:
    """Clone a remote repo into the workspace. Returns repo info dict."""
    workspace = _ensure_workspace()

    if not name:
        # Derive name from URL: git@github.com:user/repo.git -> repo
        name = url.rstrip("/").split("/")[-1].removesuffix(".git")

    dest = workspace / name
    if dest.exists():
        # Already cloned — just fetch
        code, _, stderr = await _git(str(dest), "fetch", "--all")
        if code != 0:
            raise RuntimeError(f"Fetch failed for existing repo: {stderr}")
        return await repo_info(str(dest))

    proc = await asyncio.create_subprocess_exec(
        "git", "clone", url, str(dest),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Clone failed: {stderr.decode(errors='replace')}")

    return await repo_info(str(dest))


async def repo_info(repo_path: str) -> dict:
    """Get metadata for a local repo."""
    p = Path(repo_path)
    if not p.exists() or not (p / ".git").exists():
        raise RuntimeError(f"Not a git repository: {repo_path}")

    # Default branch
    default_branch = await _detect_default_branch(repo_path)

    # Remote URL
    code, remote_url, _ = await _git(repo_path, "remote", "get-url", "origin")
    if code != 0:
        remote_url = None

    # Branch list
    code, branch_output, _ = await _git(repo_path, "branch", "--format=%(refname:short)")
    branches = [b.strip() for b in branch_output.splitlines() if b.strip()] if code == 0 else []

    # Last commit
    code, last_commit, _ = await _git(repo_path, "log", "-1", "--format=%h %s")

    return {
        "name": p.name,
        "path": str(p),
        "remote_url": remote_url,
        "default_branch": default_branch,
        "branches": branches,
        "last_commit": last_commit if code == 0 else None,
    }


async def list_repos() -> list[dict]:
    """List all repos in the workspace, plus detect any repo paths in existing tasks."""
    workspace = _ensure_workspace()
    repos = []
    for entry in sorted(workspace.iterdir()):
        if entry.is_dir() and (entry / ".git").exists():
            try:
                repos.append(await repo_info(str(entry)))
            except Exception:
                repos.append({"name": entry.name, "path": str(entry), "error": True})
    return repos


async def _detect_default_branch(repo_path: str) -> str:
    """Detect the default branch, checking HEAD, main, master in order."""
    # Try symbolic-ref of origin/HEAD first
    code, out, _ = await _git(repo_path, "symbolic-ref", "refs/remotes/origin/HEAD", "--short")
    if code == 0 and out:
        return out.replace("origin/", "")

    # Try to set it from remote
    await _git(repo_path, "remote", "set-head", "origin", "--auto")
    code, out, _ = await _git(repo_path, "symbolic-ref", "refs/remotes/origin/HEAD", "--short")
    if code == 0 and out:
        return out.replace("origin/", "")

    # Fallback: check if main or master exist
    for candidate in ("main", "master"):
        code, _, _ = await _git(repo_path, "rev-parse", "--verify", f"refs/heads/{candidate}")
        if code == 0:
            return candidate

    # Last resort: whatever HEAD points to
    code, out, _ = await _git(repo_path, "rev-parse", "--abbrev-ref", "HEAD")
    if code == 0 and out and out != "HEAD":
        return out

    return "main"


async def create_worktree(repo_path: str, branch: str, task_id: int) -> str:
    """Create a git worktree for a task. Returns the worktree path."""
    workspace = _ensure_workspace()
    worktree_dir = workspace / ".worktrees" / f"task-{task_id}"

    # Clean up existing worktree if it exists
    if worktree_dir.exists():
        await _git(repo_path, "worktree", "remove", str(worktree_dir), "--force")

    # Fetch latest
    await _git(repo_path, "fetch", "--all")

    # Does the branch already exist?
    code, _, _ = await _git(repo_path, "rev-parse", "--verify", f"refs/heads/{branch}")
    if code == 0:
        # Branch exists — create worktree from it
        code, _, stderr = await _git(repo_path, "worktree", "add", str(worktree_dir), branch)
    else:
        # Create new branch from default
        default_branch = await _detect_default_branch(repo_path)
        code, _, stderr = await _git(
            repo_path, "worktree", "add", "-b", branch, str(worktree_dir), default_branch
        )

    if code != 0:
        raise RuntimeError(f"Failed to create worktree: {stderr}")

    return str(worktree_dir)


async def remove_worktree(repo_path: str, worktree_path: str) -> None:
    """Remove a worktree (cleanup after task is done)."""
    if worktree_path and Path(worktree_path).exists():
        await _git(repo_path, "worktree", "remove", worktree_path, "--force")


async def get_commits(repo_path: str, base_branch: str, task_branch: str) -> list[dict]:
    """Get the list of commits on task_branch that aren't on base_branch."""
    code, out, _ = await _git(
        repo_path, "log", f"{base_branch}..{task_branch}",
        "--format=%H||%h||%s||%an||%ai",
    )
    if code != 0 or not out.strip():
        return []

    commits = []
    for line in out.strip().splitlines():
        parts = line.split("||", 4)
        if len(parts) == 5:
            commits.append({
                "sha": parts[0],
                "short_sha": parts[1],
                "message": parts[2],
                "author": parts[3],
                "date": parts[4],
            })
    return commits


async def get_diff_stats(repo_path: str, base_branch: str, task_branch: str) -> dict:
    """Get file-level diff stats between two branches."""
    # Stat summary
    code, stat_out, _ = await _git(
        repo_path, "diff", "--stat", f"{base_branch}..{task_branch}"
    )

    # Numstat for structured data
    code2, numstat_out, _ = await _git(
        repo_path, "diff", "--numstat", f"{base_branch}..{task_branch}"
    )

    files = []
    total_add = 0
    total_del = 0
    if code2 == 0 and numstat_out.strip():
        for line in numstat_out.strip().splitlines():
            parts = line.split("\t", 2)
            if len(parts) == 3:
                added = int(parts[0]) if parts[0] != "-" else 0
                deleted = int(parts[1]) if parts[1] != "-" else 0
                files.append({
                    "path": parts[2],
                    "additions": added,
                    "deletions": deleted,
                })
                total_add += added
                total_del += deleted

    return {
        "files": files,
        "total_additions": total_add,
        "total_deletions": total_del,
        "files_changed": len(files),
        "stat": stat_out if code == 0 else "",
    }


async def get_file_diff(repo_path: str, base_branch: str, task_branch: str, file_path: str) -> str:
    """Get the diff for a single file."""
    code, out, _ = await _git(
        repo_path, "diff", f"{base_branch}..{task_branch}", "--", file_path,
    )
    return out if code == 0 else ""
