from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

DATABASE_URL = "sqlite+aiosqlite:///./agents.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def run_startup_migrations() -> None:
    """Apply lightweight SQLite schema fixes for local development."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS objectives ("
                "id INTEGER PRIMARY KEY, "
                "title VARCHAR(200) NOT NULL, "
                "description TEXT DEFAULT '', "
                "repo_url VARCHAR(500), "
                "created_by VARCHAR(200), "
                "priority VARCHAR(20) DEFAULT 'medium', "
                "objective_state VARCHAR(20) DEFAULT 'draft', "
                "summary TEXT, "
                "recommended_next_action TEXT, "
                "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        result = await conn.execute(text("PRAGMA table_info(tasks)"))
        columns = {row[1] for row in result.fetchall()}
        if "objective_id" not in columns:
            await conn.execute(
                text(
                    "ALTER TABLE tasks ADD COLUMN objective_id INTEGER REFERENCES objectives(id)"
                )
            )
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
        if "workflow_state" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN workflow_state VARCHAR(20)")
            )
            if "workflow_status" in columns:
                await conn.execute(
                    text(
                        "UPDATE tasks SET workflow_state = CASE "
                        "WHEN workflow_status = 'needs_review' THEN 'needs_review' "
                        "WHEN workflow_status = 'completed' THEN 'completed' "
                        "WHEN workflow_status = 'failed' THEN 'failed' "
                        "WHEN workflow_status = 'paused' THEN 'waiting_for_user' "
                        "ELSE 'ready' END"
                    )
                )
            else:
                await conn.execute(text("UPDATE tasks SET workflow_state = 'ready'"))
        if "runtime_state" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN runtime_state VARCHAR(20)")
            )
            if "runtime_status" in columns:
                await conn.execute(
                    text(
                        "UPDATE tasks SET runtime_state = CASE "
                        "WHEN runtime_status = 'running' THEN 'running' "
                        "WHEN runtime_status = 'stopped' THEN 'stopped' "
                        "WHEN runtime_status = 'failed' THEN 'failed' "
                        "ELSE 'idle' END"
                    )
                )
            else:
                await conn.execute(text("UPDATE tasks SET runtime_state = 'idle'"))
        if "task_kind" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN task_kind VARCHAR(20)")
            )
            await conn.execute(text("UPDATE tasks SET task_kind = 'investigate'"))
        if "target_type" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN target_type VARCHAR(20)")
            )
            await conn.execute(
                text(
                    "UPDATE tasks SET target_type = CASE "
                    "WHEN branch IS NOT NULL OR base_branch IS NOT NULL THEN 'branch_diff' "
                    "ELSE 'repo_head' END"
                )
            )
        if "commit_start" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN commit_start VARCHAR(64)")
            )
        if "commit_end" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN commit_end VARCHAR(64)")
            )
        if "path_scope" not in columns:
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN path_scope TEXT"))
        if "active_run_id" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN active_run_id INTEGER")
            )
        if "priority" not in columns:
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN priority VARCHAR(20)"))
            await conn.execute(text("UPDATE tasks SET priority = 'medium'"))
        if "blocked_reason" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN blocked_reason TEXT")
            )
        if "result_summary" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN result_summary TEXT")
            )
        if "failure_reason" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN failure_reason TEXT")
            )
        if "next_action_hint" not in columns:
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN next_action_hint TEXT")
            )
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
                "provider VARCHAR(50), "
                "trigger_type VARCHAR(32) DEFAULT 'manual_start', "
                "status VARCHAR(20) NOT NULL, "
                "run_state VARCHAR(20) DEFAULT 'running', "
                "prompt TEXT, "
                "dispatch_snapshot TEXT, "
                "prompt_summary TEXT, "
                "exit_code INTEGER, "
                "error_type VARCHAR(100), "
                "error TEXT, "
                "output_summary TEXT, "
                "raw_output_ref TEXT, "
                "started_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                "finished_at DATETIME)"
            )
        )
        runs_result = await conn.execute(text("PRAGMA table_info(runs)"))
        run_columns = {row[1] for row in runs_result.fetchall()}
        if "provider" not in run_columns:
            await conn.execute(text("ALTER TABLE runs ADD COLUMN provider VARCHAR(50)"))
        if "trigger_type" not in run_columns:
            await conn.execute(
                text(
                    "ALTER TABLE runs ADD COLUMN trigger_type VARCHAR(32) DEFAULT 'manual_start'"
                )
            )
        if "run_state" not in run_columns:
            await conn.execute(
                text("ALTER TABLE runs ADD COLUMN run_state VARCHAR(20) DEFAULT 'running'")
            )
            await conn.execute(
                text(
                    "UPDATE runs SET run_state = CASE "
                    "WHEN status = 'failed' THEN 'failed' "
                    "WHEN status = 'running' THEN 'running' "
                    "WHEN status = 'stopped' THEN 'cancelled' "
                    "ELSE 'completed' END"
                )
            )
        if "dispatch_snapshot" not in run_columns:
            await conn.execute(
                text("ALTER TABLE runs ADD COLUMN dispatch_snapshot TEXT")
            )
        if "prompt_summary" not in run_columns:
            await conn.execute(text("ALTER TABLE runs ADD COLUMN prompt_summary TEXT"))
        if "error_type" not in run_columns:
            await conn.execute(text("ALTER TABLE runs ADD COLUMN error_type VARCHAR(100)"))
        if "output_summary" not in run_columns:
            await conn.execute(text("ALTER TABLE runs ADD COLUMN output_summary TEXT"))
        if "raw_output_ref" not in run_columns:
            await conn.execute(text("ALTER TABLE runs ADD COLUMN raw_output_ref TEXT"))
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS threads ("
                "id INTEGER PRIMARY KEY, "
                "task_id INTEGER NOT NULL UNIQUE REFERENCES tasks(id), "
                "provider VARCHAR(50) NOT NULL, "
                "provider_thread_id VARCHAR(200), "
                "thread_state VARCHAR(20) DEFAULT 'idle', "
                "context_summary TEXT, "
                "last_message_at DATETIME, "
                "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS decisions ("
                "id INTEGER PRIMARY KEY, "
                "objective_id INTEGER REFERENCES objectives(id), "
                "task_id INTEGER REFERENCES tasks(id), "
                "decision_type VARCHAR(32) NOT NULL, "
                "decision_state VARCHAR(20) DEFAULT 'open', "
                "question TEXT NOT NULL, "
                "options TEXT, "
                "recommended_option TEXT, "
                "chosen_option TEXT, "
                "answered_by VARCHAR(200), "
                "answered_at DATETIME, "
                "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
        )


async def get_db():
    async with async_session() as session:
        yield session
