import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
from pathlib import Path
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, messages_from_dict, messages_to_dict

from app.ai.workflows.graph_state import GraphState
from app.domain.models.user_profile import UserProfile


class UserSessionRepository:
    """Small local SQLite store for workflow memory scoped by user and project."""

    def __init__(self, database_path: Path = Path("data/hpa.sqlite3")) -> None:
        self.database_path = database_path
        self.templates_path = database_path.parent / "templates"
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.templates_path.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS project_sessions (
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    project_name TEXT NOT NULL DEFAULT 'Project without name',
                    thread_id TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, project_id)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    professional_role TEXT NOT NULL DEFAULT 'resident_physician',
                    preferred_language TEXT NOT NULL DEFAULT 'en',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS auth_tokens (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS presentation_templates (
                    template_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            self._ensure_project_name_column(connection)
            self._ensure_user_profile_columns(connection)
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
        return row[0], self._deserialize_state(json.loads(row[1]))

    def save(
        self,
        user_id: str,
        project_id: str,
        thread_id: str,
        state: GraphState,
        project_name: str | None = None,
    ) -> None:
        payload = json.dumps(self._serialize_state(state))
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO project_sessions (user_id, project_id, project_name, thread_id, state_json, updated_at)
                   VALUES (?, ?, COALESCE(NULLIF(?, ''), ?), ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(user_id, project_id) DO UPDATE SET
                   project_name = CASE
                       WHEN ? = '' THEN project_sessions.project_name
                       ELSE excluded.project_name
                   END,
                   thread_id = excluded.thread_id,
                   state_json = excluded.state_json,
                   updated_at = CURRENT_TIMESTAMP""",
                (user_id, project_id, project_name or "", project_id, thread_id, payload, project_name or ""),
            )

    def create_empty(self, user_id: str, project_id: str, project_name: str | None = None) -> tuple[str, GraphState]:
        thread_id, state = str(uuid4()), GraphState()
        self.save(user_id, project_id, thread_id, state, project_name)
        return thread_id, state

    def list_projects(self, user_id: str) -> list[dict[str, str]]:
        """Return the user's projects, most recently updated first."""
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT project_id, project_name FROM project_sessions
                   WHERE user_id = ? ORDER BY updated_at DESC, project_id ASC""",
                (user_id,),
            ).fetchall()
        return [{"id": row[0], "name": row[1]} for row in rows]

    def list_project_ids(self, user_id: str) -> list[str]:
        """Compatibility helper for the legacy Streamlit interface."""
        return [project["id"] for project in self.list_projects(user_id)]

    def register_user(self, user_id: str, password: str, profile: UserProfile | None = None) -> None:
        profile = profile or UserProfile()
        salt = secrets.token_bytes(16)
        password_hash = self._hash_password(password, salt)
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO users
                       (user_id, password_salt, password_hash, professional_role, preferred_language)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        user_id,
                        self._encode(salt),
                        self._encode(password_hash),
                        profile.professional_role,
                        profile.preferred_language,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Cet identifiant utilisateur existe déjà.") from exc

    def authenticate_user(self, user_id: str, password: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT password_salt, password_hash FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return False
        actual = self._hash_password(password, self._decode(row[0]))
        return hmac.compare_digest(actual, self._decode(row[1]))

    def reset_password_without_verification(self, user_id: str, password: str) -> None:
        """Local-only recovery requested by the product owner; never expose publicly."""
        salt = secrets.token_bytes(16)
        password_hash = self._hash_password(password, salt)
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE users SET password_salt = ?, password_hash = ? WHERE user_id = ?""",
                (self._encode(salt), self._encode(password_hash), user_id),
            )
            connection.execute("DELETE FROM auth_tokens WHERE user_id = ?", (user_id,))
        if cursor.rowcount == 0:
            raise ValueError("User not found.")

    def get_user_profile(self, user_id: str) -> UserProfile:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT professional_role, preferred_language FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row is None:
            raise ValueError("User not found.")
        return UserProfile(professional_role=row[0], preferred_language=row[1])

    def update_user_profile(self, user_id: str, profile: UserProfile) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE users SET professional_role = ?, preferred_language = ?
                   WHERE user_id = ?""",
                (profile.professional_role, profile.preferred_language, user_id),
            )
        if cursor.rowcount == 0:
            raise ValueError("User not found.")

    def create_auth_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self._connect() as connection:
            connection.execute("DELETE FROM auth_tokens WHERE expires_at <= CURRENT_TIMESTAMP")
            connection.execute(
                """INSERT INTO auth_tokens (token_hash, user_id, expires_at)
                   VALUES (?, ?, datetime('now', '+12 hours'))""",
                (token_hash, user_id),
            )
        return token

    def user_for_token(self, token: str) -> str | None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self._connect() as connection:
            row = connection.execute(
                """SELECT user_id FROM auth_tokens
                   WHERE token_hash = ? AND expires_at > CURRENT_TIMESTAMP""",
                (token_hash,),
            ).fetchone()
        return row[0] if row else None

    def delete_project(self, user_id: str, project_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM project_sessions WHERE user_id = ? AND project_id = ?",
                (user_id, project_id),
            )
        return cursor.rowcount > 0

    def delete_user(self, user_id: str) -> None:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT stored_filename FROM presentation_templates WHERE user_id = ?", (user_id,)
            ).fetchall()
            connection.execute("DELETE FROM auth_tokens WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM project_sessions WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM presentation_templates WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        for row in rows:
            (self.templates_path / row[0]).unlink(missing_ok=True)

    def save_presentation_template(self, user_id: str, filename: str, content: bytes) -> dict[str, str]:
        template_id = str(uuid4())
        safe_filename = Path(filename).name
        stored_filename = f"{template_id}.pptx"
        (self.templates_path / stored_filename).write_bytes(content)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO presentation_templates (template_id, user_id, filename, stored_filename)
                   VALUES (?, ?, ?, ?)""",
                (template_id, user_id, safe_filename, stored_filename),
            )
        return {"id": template_id, "filename": safe_filename}

    def list_presentation_templates(self, user_id: str) -> list[dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT template_id, filename FROM presentation_templates
                   WHERE user_id = ? ORDER BY created_at DESC""",
                (user_id,),
            ).fetchall()
        return [{"id": row[0], "filename": row[1]} for row in rows]

    def presentation_template_path(self, user_id: str, template_id: str) -> Path | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT stored_filename FROM presentation_templates
                   WHERE user_id = ? AND template_id = ?""",
                (user_id, template_id),
            ).fetchone()
        if row is None:
            return None
        path = self.templates_path / row[0]
        return path if path.is_file() else None

    @staticmethod
    def _serialize_state(state: GraphState) -> dict[str, object]:
        payload = state.model_dump(mode="json", exclude={"messages"})
        payload["messages"] = messages_to_dict(state.messages)
        return payload

    @staticmethod
    def _deserialize_state(payload: dict[str, object]) -> GraphState:
        raw_messages = payload.get("messages", [])
        if isinstance(raw_messages, list):
            try:
                payload["messages"] = messages_from_dict(raw_messages)
            except (KeyError, TypeError, ValueError):
                # Compatibility with JSON states saved before LangChain's native serializer.
                legacy_messages = []
                for item in raw_messages:
                    if not isinstance(item, dict):
                        continue
                    message_type = item.get("type")
                    content = item.get("content")
                    if message_type == "human" and isinstance(content, (str, list)):
                        legacy_messages.append(HumanMessage(content=content))
                    elif message_type == "ai" and isinstance(content, (str, list)):
                        legacy_messages.append(AIMessage(content=content))
                payload["messages"] = legacy_messages
        return GraphState.model_validate(payload)

    @staticmethod
    def _ensure_project_name_column(connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(project_sessions)")}
        if "project_name" not in columns:
            connection.execute("ALTER TABLE project_sessions ADD COLUMN project_name TEXT")
            connection.execute(
                "UPDATE project_sessions SET project_name = project_id WHERE project_name IS NULL"
            )

    @staticmethod
    def _ensure_user_profile_columns(connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        if "professional_role" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN professional_role TEXT NOT NULL DEFAULT 'resident_physician'")
        if "preferred_language" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN preferred_language TEXT NOT NULL DEFAULT 'en'")

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
               (user_id, project_id, project_name, thread_id, state_json, updated_at)
               SELECT user_id, 'default', 'Default Project', thread_id, state_json, updated_at
               FROM user_sessions"""
        )

    @staticmethod
    def _hash_password(password: str, salt: bytes) -> bytes:
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16_384, r=8, p=1)

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.b64encode(value).decode("ascii")

    @staticmethod
    def _decode(value: str) -> bytes:
        return base64.b64decode(value.encode("ascii"))

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)
