import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.database import get_db
from app.models import Role
from app.schemas import RoleOut
from app.services.roles import load_template, sync_roles_from_disk

router = APIRouter(prefix="/roles", tags=["roles"])


def _role_to_out(role: Role) -> dict:
    """Convert a Role model to RoleOut-compatible dict."""
    can_spawn = None
    if role.can_spawn:
        can_spawn = json.loads(role.can_spawn)
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "can_spawn": can_spawn,
    }


@router.get("", response_model=list[RoleOut])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    result = await db.execute(select(Role).order_by(Role.name))
    roles = result.scalars().all()
    return [_role_to_out(r) for r in roles]


@router.get("/{name}")
async def get_role(
    name: str,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    result = await db.execute(select(Role).where(Role.name == name))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(404, "Role not found")

    template_body = load_template(role.template_path)
    out = _role_to_out(role)
    out["template"] = template_body
    return out


@router.post("/sync")
async def sync_roles(
    db: AsyncSession = Depends(get_db),
    user: str = Depends(require_auth),
):
    count = await sync_roles_from_disk(db)
    return {"synced": count}
