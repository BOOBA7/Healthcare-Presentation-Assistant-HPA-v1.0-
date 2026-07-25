import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from app.ai.workflows.graph_state import GraphState


class UserSessionRepository:
    """Small local SQLite store for user-scoped workflow memory."""

    def __init__(self, database_path: Path = Path("data/hpa.sqlite3")) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS user_sessions (
                    user_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )

    def load(self, user_id: str) -> tuple[str, GraphState] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT thread_id, state_json FROM user_sessions WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return None
        return row[0], GraphState.model_validate(json.loads(row[1]))

    def save(self, user_id: str, thread_id: str, state: GraphState) -> None:
        payload = json.dumps(state.model_dump(mode="json"))
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO user_sessions (user_id, thread_id, state_json, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(user_id) DO UPDATE SET
                   thread_id = excluded.thread_id,
                   state_json = excluded.state_json,
                   updated_at = CURRENT_TIMESTAMP""",
                (user_id, thread_id, payload),
            )

    def create_empty(self, user_id: str) -> tuple[str, GraphState]:
        thread_id, state = str(uuid4()), GraphState()
        self.save(user_id, thread_id, state)
        return thread_id, state

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)
