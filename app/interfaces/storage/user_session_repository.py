import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from app.ai.workflows.graph_state import GraphState


class UserSessionRepository:
    """Small local SQLite store for workflow memory scoped by user and project."""

    def __init__(self, database_path: Path = Path("data/hpa.sqlite3")) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS project_sessions (
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, project_id)
                )"""
            )
            self._migrate_legacy_user_sessions(connection)

    def load(self, user_id: str, project_id: str) -> tuple[str, GraphState] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT thread_id, state_json FROM project_sessions
                   WHERE user_id = ? AND project_id = ?""",
                (user_id, project_id),
            ).fetchone()
        if row is None:
            return None
        return row[0], GraphState.model_validate(json.loads(row[1]))

    def save(self, user_id: str, project_id: str, thread_id: str, state: GraphState) -> None:
        payload = json.dumps(state.model_dump(mode="json"))
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO project_sessions (user_id, project_id, thread_id, state_json, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(user_id, project_id) DO UPDATE SET
                   thread_id = excluded.thread_id,
                   state_json = excluded.state_json,
                   updated_at = CURRENT_TIMESTAMP""",
                (user_id, project_id, thread_id, payload),
            )

    def create_empty(self, user_id: str, project_id: str) -> tuple[str, GraphState]:
        thread_id, state = str(uuid4()), GraphState()
        self.save(user_id, project_id, thread_id, state)
        return thread_id, state

    def list_project_ids(self, user_id: str) -> list[str]:
        """Return the user's projects, most recently updated first."""
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT project_id FROM project_sessions
                   WHERE user_id = ? ORDER BY updated_at DESC, project_id ASC""",
                (user_id,),
            ).fetchall()
        return [row[0] for row in rows]

    @staticmethod
    def _migrate_legacy_user_sessions(connection: sqlite3.Connection) -> None:
        """Keep existing one-project user sessions accessible after the schema upgrade."""
        legacy_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'user_sessions'"
        ).fetchone()
        if legacy_table is None:
            return
        connection.execute(
            """INSERT OR IGNORE INTO project_sessions
               (user_id, project_id, thread_id, state_json, updated_at)
               SELECT user_id, 'default', thread_id, state_json, updated_at
               FROM user_sessions"""
        )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)
