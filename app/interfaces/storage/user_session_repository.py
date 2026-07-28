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
from app.application.services.resource_library import ensure_resource_library
from app.domain.exceptions.concurrent_modification_error import ConcurrentModificationError
from app.domain.models.resource import Resource
from app.domain.models.user_profile import UserProfile


class UserSessionRepository:
    """Small local SQLite store for workflow memory scoped by user and project."""

    def __init__(self, database_path: Path = Path("data/hpa.sqlite3")) -> None:
        self.database_path = database_path
        self.templates_path = database_path.parent / "templates"
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.templates_path.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
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
            connection.execute(
                """CREATE TABLE IF NOT EXISTS project_events (
                    event_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS project_jobs (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    stage TEXT NOT NULL DEFAULT 'queued',
                    result_json TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS project_resources (
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, project_id, resource_id)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS project_resource_pages (
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    page_text TEXT NOT NULL,
                    PRIMARY KEY (user_id, project_id, resource_id, page_number)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS project_resource_chunks (
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    chunk_position INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    PRIMARY KEY (user_id, project_id, resource_id, page_number, chunk_position)
                )"""
            )
            connection.execute(
                """CREATE INDEX IF NOT EXISTS idx_project_jobs_project
                   ON project_jobs (user_id, project_id, created_at DESC)"""
            )
            connection.execute(
                """CREATE INDEX IF NOT EXISTS idx_project_events_project
                   ON project_events (user_id, project_id, created_at)"""
            )
            self._ensure_project_name_column(connection)
            self._ensure_project_revision_column(connection)
            self._ensure_user_profile_columns(connection)
            self._migrate_legacy_user_sessions(connection)
            self._recover_interrupted_jobs(connection)

    def load(self, user_id: str, project_id: str) -> tuple[str, GraphState] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT thread_id, state_json, revision FROM project_sessions
                   WHERE user_id = ? AND project_id = ?""",
                (user_id, project_id),
            ).fetchone()
            resources = self._load_resources(connection, user_id, project_id)
        if row is None:
            return None
        state = self._deserialize_state(json.loads(row[1]))
        if resources:
            state.resource_library = resources
        state.project_revision = row[2]
        return row[0], state

    def save(
        self,
        user_id: str,
        project_id: str,
        thread_id: str,
        state: GraphState,
        project_name: str | None = None,
    ) -> None:
        with self._connect() as connection:
            self._save_project_row(connection, user_id, project_id, thread_id, state, project_name)

    def save_with_event(
        self,
        user_id: str,
        project_id: str,
        thread_id: str,
        state: GraphState,
        event_type: str,
        actor: str,
        payload: dict[str, object] | None = None,
        project_name: str | None = None,
    ) -> None:
        """Persist workflow state and its audit event in one transaction."""
        with self._connect() as connection:
            self._save_project_row(connection, user_id, project_id, thread_id, state, project_name)
            self._insert_event(connection, user_id, project_id, event_type, actor, payload)

    def create_empty(self, user_id: str, project_id: str, project_name: str | None = None) -> tuple[str, GraphState]:
        thread_id, state = str(uuid4()), GraphState()
        self.save_with_event(
            user_id,
            project_id,
            thread_id,
            state,
            "PROJECT_CREATED",
            "system",
            {"project_name": project_name or project_id},
            project_name,
        )
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
            for table in ("project_resource_chunks", "project_resource_pages", "project_resources", "project_jobs"):
                connection.execute(
                    f"DELETE FROM {table} WHERE user_id = ? AND project_id = ?",
                    (user_id, project_id),
                )
            connection.execute(
                "DELETE FROM project_events WHERE user_id = ? AND project_id = ?",
                (user_id, project_id),
            )
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
            connection.execute("DELETE FROM project_resource_chunks WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM project_resource_pages WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM project_resources WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM project_jobs WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM project_sessions WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM project_events WHERE user_id = ?", (user_id,))
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

    def record_event(
        self,
        user_id: str,
        project_id: str,
        event_type: str,
        actor: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        """Append an immutable business/audit event for a Project."""
        with self._connect() as connection:
            self._insert_event(connection, user_id, project_id, event_type, actor, payload)

    def list_events(self, user_id: str, project_id: str, limit: int = 200) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT event_id, event_type, actor, payload_json, created_at
                   FROM project_events WHERE user_id = ? AND project_id = ?
                   ORDER BY created_at DESC, rowid DESC LIMIT ?""",
                (user_id, project_id, limit),
            ).fetchall()
        return [
            {
                "id": row[0],
                "event_type": row[1],
                "actor": row[2],
                "payload": json.loads(row[3]),
                "created_at": row[4],
            }
            for row in rows
        ]

    def create_job(self, user_id: str, project_id: str, domain: str) -> dict[str, object]:
        """Create a durable asynchronous job record before scheduling work."""
        job_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO project_jobs (job_id, user_id, project_id, domain, status, progress, stage)
                   VALUES (?, ?, ?, ?, 'queued', 0, 'queued')""",
                (job_id, user_id, project_id, domain),
            )
        return self.get_job(user_id, job_id) or {}

    def update_job(
        self,
        user_id: str,
        job_id: str,
        *,
        status: str,
        progress: int,
        stage: str,
        result: dict[str, object] | None = None,
        error_message: str | None = None,
    ) -> None:
        """Persist monotonic job progress and terminal result metadata."""
        if not 0 <= progress <= 100:
            raise ValueError("Job progress must be between 0 and 100.")
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE project_jobs SET status = ?, progress = ?, stage = ?, result_json = ?,
                   error_message = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE job_id = ? AND user_id = ?""",
                (status, progress, stage, json.dumps(result, default=str) if result is not None else None,
                 error_message, job_id, user_id),
            )
        if cursor.rowcount == 0:
            raise ValueError("Job not found.")

    def get_job(self, user_id: str, job_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT job_id, project_id, domain, status, progress, stage, result_json, error_message,
                   created_at, updated_at FROM project_jobs WHERE job_id = ? AND user_id = ?""",
                (job_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "job_id": row[0], "project_id": row[1], "domain": row[2], "status": row[3],
            "progress": row[4], "stage": row[5], "result": json.loads(row[6]) if row[6] else None,
            "error": row[7], "created_at": row[8], "updated_at": row[9],
        }

    @staticmethod
    def _serialize_state(state: GraphState) -> dict[str, object]:
        # Resource documents/pages are persisted in dedicated tables. Keeping
        # them out of this state snapshot prevents every chat turn from
        # rewriting all extracted PDF content.
        payload = state.model_dump(mode="json", exclude={"messages", "resource_library"})
        payload["messages"] = messages_to_dict(state.messages)
        return payload

    @staticmethod
    def _deserialize_state(payload: dict[str, object]) -> GraphState:
        # Projects saved before the library split embed source PDF text in the
        # presentation. Preserve it once so migration can safely normalize it.
        presentation = payload.get("presentation")
        if isinstance(presentation, dict) and not payload.get("resource_library"):
            resources = presentation.get("resources")
            if isinstance(resources, list):
                payload["resource_library"] = resources
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
    def _ensure_project_revision_column(connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(project_sessions)")}
        if "revision" not in columns:
            connection.execute("ALTER TABLE project_sessions ADD COLUMN revision INTEGER NOT NULL DEFAULT 0")

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
    def _recover_interrupted_jobs(connection: sqlite3.Connection) -> None:
        """Do not leave browser polling stuck after a local server restart."""
        connection.execute(
            """UPDATE project_jobs SET status = 'failed', stage = 'interrupted',
               error_message = 'The local server restarted before this job completed.',
               updated_at = CURRENT_TIMESTAMP
               WHERE status IN ('queued', 'running')"""
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
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _save_project_row(
        self,
        connection: sqlite3.Connection,
        user_id: str,
        project_id: str,
        thread_id: str,
        state: GraphState,
        project_name: str | None,
    ) -> None:
        ensure_resource_library(state)
        existing = connection.execute(
            "SELECT revision FROM project_sessions WHERE user_id = ? AND project_id = ?",
            (user_id, project_id),
        ).fetchone()
        current_revision = existing[0] if existing else None
        if current_revision is not None and state.project_revision != current_revision:
            raise ConcurrentModificationError()

        next_revision = 1 if current_revision is None else current_revision + 1
        state.project_revision = next_revision
        self._sync_resources(connection, user_id, project_id, state.resource_library)
        payload = json.dumps(self._serialize_state(state))

        if current_revision is None:
            connection.execute(
                """INSERT INTO project_sessions
                   (user_id, project_id, project_name, thread_id, state_json, revision, updated_at)
                   VALUES (?, ?, COALESCE(NULLIF(?, ''), ?), ?, ?, ?, CURRENT_TIMESTAMP)""",
                (user_id, project_id, project_name or "", project_id, thread_id, payload, next_revision),
            )
            return

        cursor = connection.execute(
            """UPDATE project_sessions SET
               project_name = CASE WHEN ? = '' THEN project_name ELSE ? END,
               thread_id = ?, state_json = ?, revision = ?, updated_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND project_id = ? AND revision = ?""",
            (
                project_name or "", project_name or "", thread_id, payload, next_revision,
                user_id, project_id, current_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise ConcurrentModificationError()

    @staticmethod
    def _resource_pages(resource: Resource) -> list[dict[str, object]]:
        pages = [
            {"page": page["page"], "text": page["text"]}
            for page in resource.extracted_pages
            if isinstance(page.get("page"), int) and isinstance(page.get("text"), str)
        ]
        if not pages and resource.extracted_text:
            pages = [{"page": 1, "text": resource.extracted_text}]
        return pages

    @staticmethod
    def _chunks_for_pages(pages: list[dict[str, object]]) -> list[tuple[int, int, str]]:
        chunks: list[tuple[int, int, str]] = []
        for page in pages:
            page_number, page_text = page["page"], " ".join(str(page["text"]).split())
            for position, start in enumerate(range(0, len(page_text), 1200)):
                chunk = page_text[start : start + 1200]
                if chunk:
                    chunks.append((int(page_number), position, chunk))
        return chunks

    def _sync_resources(
        self, connection: sqlite3.Connection, user_id: str, project_id: str, resources: list[Resource]
    ) -> None:
        existing = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT resource_id, content_hash FROM project_resources WHERE user_id = ? AND project_id = ?",
                (user_id, project_id),
            )
        }
        incoming_ids = {resource.id for resource in resources}
        removed_ids = set(existing).difference(incoming_ids)
        for resource_id in removed_ids:
            for table in ("project_resource_chunks", "project_resource_pages", "project_resources"):
                connection.execute(
                    f"DELETE FROM {table} WHERE user_id = ? AND project_id = ? AND resource_id = ?",
                    (user_id, project_id, resource_id),
                )

        for resource in resources:
            metadata = resource.model_dump(mode="json", exclude={"extracted_text", "extracted_pages"})
            pages = self._resource_pages(resource)
            canonical = json.dumps({"metadata": metadata, "pages": pages}, sort_keys=True, ensure_ascii=False)
            content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if existing.get(resource.id) == content_hash:
                continue
            connection.execute(
                """INSERT INTO project_resources (user_id, project_id, resource_id, metadata_json, content_hash)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, project_id, resource_id) DO UPDATE SET
                   metadata_json = excluded.metadata_json, content_hash = excluded.content_hash,
                   updated_at = CURRENT_TIMESTAMP""",
                (user_id, project_id, resource.id, json.dumps(metadata), content_hash),
            )
            connection.execute(
                "DELETE FROM project_resource_pages WHERE user_id = ? AND project_id = ? AND resource_id = ?",
                (user_id, project_id, resource.id),
            )
            connection.execute(
                "DELETE FROM project_resource_chunks WHERE user_id = ? AND project_id = ? AND resource_id = ?",
                (user_id, project_id, resource.id),
            )
            connection.executemany(
                """INSERT INTO project_resource_pages
                   (user_id, project_id, resource_id, page_number, page_text) VALUES (?, ?, ?, ?, ?)""",
                [(user_id, project_id, resource.id, int(page["page"]), str(page["text"])) for page in pages],
            )
            connection.executemany(
                """INSERT INTO project_resource_chunks
                   (user_id, project_id, resource_id, page_number, chunk_position, chunk_text)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (user_id, project_id, resource.id, page, position, text)
                    for page, position, text in self._chunks_for_pages(pages)
                ],
            )

    @staticmethod
    def _load_resources(connection: sqlite3.Connection, user_id: str, project_id: str) -> list[Resource]:
        rows = connection.execute(
            """SELECT resource_id, metadata_json FROM project_resources
               WHERE user_id = ? AND project_id = ? ORDER BY updated_at, resource_id""",
            (user_id, project_id),
        ).fetchall()
        resources: list[Resource] = []
        for resource_id, metadata_json in rows:
            pages = connection.execute(
                """SELECT page_number, page_text FROM project_resource_pages
                   WHERE user_id = ? AND project_id = ? AND resource_id = ? ORDER BY page_number""",
                (user_id, project_id, resource_id),
            ).fetchall()
            metadata = json.loads(metadata_json)
            extracted_pages = [{"page": page, "text": text} for page, text in pages]
            resources.append(
                Resource.model_validate(
                    {
                        **metadata,
                        "extracted_pages": extracted_pages,
                        "extracted_text": "\n".join(str(page["text"]) for page in extracted_pages),
                    }
                )
            )
        return resources

    @staticmethod
    def _insert_event(
        connection: sqlite3.Connection,
        user_id: str,
        project_id: str,
        event_type: str,
        actor: str,
        payload: dict[str, object] | None,
    ) -> None:
        connection.execute(
            """INSERT INTO project_events
               (event_id, user_id, project_id, event_type, actor, payload_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                str(uuid4()), user_id, project_id, event_type, actor,
                json.dumps(payload or {}, default=str),
            ),
        )
