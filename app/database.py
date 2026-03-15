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
        if "codex_session_id" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN codex_session_id VARCHAR(100)")
            )


async def get_db():
    async with async_session() as session:
        yield session
