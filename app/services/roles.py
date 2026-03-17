"""Role template loading and disk-to-DB synchronisation."""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role

logger = logging.getLogger("roles")

ROLES_DIR = Path(__file__).parent.parent.parent / "roles"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML-like frontmatter from a markdown file.

    Returns (metadata dict, body text).  Uses a simple parser to avoid
    adding a PyYAML dependency.
    """
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    meta: dict = {}
    for line in parts[1].strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^(\w+):\s*(.+)$", line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            # Parse list values like [developer, architect]
            if value.startswith("[") and value.endswith("]"):
                items = [v.strip() for v in value[1:-1].split(",") if v.strip()]
                meta[key] = items
            else:
                meta[key] = value

    return meta, parts[2].strip()


def load_template(template_path: str) -> str:
    """Load a role template file, return the body (after frontmatter)."""
    path = ROLES_DIR / template_path
    if not path.exists():
        raise FileNotFoundError(f"Role template not found: {path}")
    text = path.read_text(encoding="utf-8")
    _, body = _parse_frontmatter(text)
    return body


async def load_role_for_task(db: AsyncSession, role_id: int) -> Optional[Role]:
    """Load a Role by ID."""
    return await db.get(Role, role_id)


def build_effective_prompt(role_template: str, task_description: str) -> str:
    """Combine a role template with the task description into a single prompt."""
    return f"{role_template}\n\n---\n\n## Your Task\n\n{task_description}"


async def sync_roles_from_disk(db: AsyncSession) -> int:
    """Scan the roles/ directory and upsert into the database.

    Returns the number of roles synced.
    """
    if not ROLES_DIR.is_dir():
        logger.info("No roles/ directory found — skipping sync")
        return 0

    count = 0
    for path in sorted(ROLES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, _ = _parse_frontmatter(text)

        name = meta.get("name", path.stem)
        description = meta.get("description", "")
        can_spawn = meta.get("can_spawn")

        # Upsert
        result = await db.execute(select(Role).where(Role.name == name))
        role = result.scalar_one_or_none()

        can_spawn_json = json.dumps(can_spawn) if can_spawn else None

        if role:
            role.description = description
            role.template_path = path.name
            role.can_spawn = can_spawn_json
        else:
            role = Role(
                name=name,
                description=description,
                template_path=path.name,
                can_spawn=can_spawn_json,
            )
            db.add(role)

        count += 1

    await db.commit()
    logger.info("Synced %d role(s) from disk", count)
    return count
