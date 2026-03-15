"""API routes for repository management."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_auth
from app.services.repo import clone_repo, list_repos, repo_info

router = APIRouter(prefix="/repos", tags=["repos"])


class CloneRequest(BaseModel):
    url: str
    name: Optional[str] = None


@router.get("")
async def get_repos(user: str = Depends(require_auth)):
    """List all repos in the agent workspace."""
    return await list_repos()


@router.post("", status_code=201)
async def clone(body: CloneRequest, user: str = Depends(require_auth)):
    """Clone a repo into the agent workspace (or fetch if it already exists)."""
    try:
        return await clone_repo(body.url, body.name)
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@router.get("/{name}")
async def get_repo(name: str, user: str = Depends(require_auth)):
    """Get info about a specific repo by workspace name."""
    from app.services.repo import WORKSPACE_DIR
    repo_path = str(WORKSPACE_DIR / name)
    try:
        return await repo_info(repo_path)
    except RuntimeError as e:
        raise HTTPException(404, str(e))
