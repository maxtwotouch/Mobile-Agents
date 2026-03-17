from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

DATABASE_URL = "sqlite+aiosqlite:///./agents.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def run_startup_migrations() -> None:
    """Apply lightweight SQLite schema fixes for local development."""
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(tasks)"))
        columns = {row[1] for row in result.fetchall()}
        if "workflow_status" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN workflow_status VARCHAR(20)")
            )
            if "status" in columns:
                await conn.execute(text("UPDATE tasks SET workflow_status = status"))
            else:
                await conn.execute(
                    text("UPDATE tasks SET workflow_status = 'pending'")
                )
        if "runtime_status" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN runtime_status VARCHAR(20)")
            )
            if "status" in columns:
                await conn.execute(
                    text(
                        "UPDATE tasks SET runtime_status = CASE "
                        "WHEN status = 'running' THEN 'running' "
                        "WHEN status = 'failed' THEN 'failed' "
                        "ELSE 'idle' END"
                    )
                )
            else:
                await conn.execute(text("UPDATE tasks SET runtime_status = 'idle'"))
        if "thread_id" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN thread_id VARCHAR(200)")
            )
        if "runner_id" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN runner_id VARCHAR(100)")
            )
            if "tmux_session" in columns:
                await conn.execute(text("UPDATE tasks SET runner_id = tmux_session"))
        if "codex_session_id" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN codex_session_id VARCHAR(100)")
            )
        if "worktree_path" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN worktree_path VARCHAR(500)")
            )
        if "base_branch" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN base_branch VARCHAR(200)")
            )
        if "last_run_started_at" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN last_run_started_at DATETIME")
            )
        if "last_run_finished_at" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN last_run_finished_at DATETIME")
            )
        if "last_heartbeat_at" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN last_heartbeat_at DATETIME")
            )
        if "role_id" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN role_id INTEGER REFERENCES roles(id)")
            )
        if "parent_task_id" not in columns:
            await conn.execute(
                text(
                    "ALTER TABLE tasks ADD COLUMN parent_task_id INTEGER REFERENCES tasks(id)"
                )
            )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS runs ("
                "id INTEGER PRIMARY KEY, "
                "task_id INTEGER NOT NULL REFERENCES tasks(id), "
                "thread_id VARCHAR(200), "
                "runner_id VARCHAR(100) NOT NULL, "
                "status VARCHAR(20) NOT NULL, "
                "prompt TEXT, "
                "exit_code INTEGER, "
                "error TEXT, "
                "started_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                "finished_at DATETIME)"
            )
        )


async def get_db():
    async with async_session() as session:
        yield session
