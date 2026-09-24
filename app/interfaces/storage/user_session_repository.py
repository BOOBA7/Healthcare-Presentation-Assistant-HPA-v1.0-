import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
from pathlib import Path
from app.application.services.prototype_policy import PrototypePolicy
from app.application.services.source_screening import SourceScreening
from app.application.services.source_document import SourceDocument
from app.domain.exceptions.workflow_error import WorkflowError
from collections.abc import Iterable
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, messages_from_dict, messages_to_dict

from app.ai.workflows.graph_state import GraphState
from app.application.services.resource_library import ensure_resource_library, resource_selection
from app.domain.exceptions.concurrent_modification_error import ConcurrentModificationError
from app.domain.exceptions.project_job_running_error import ProjectJobRunningError
from app.domain.models.resource import Resource
from app.domain.models.resource_chunk import ResourceChunk
from app.domain.models.user_profile import UserProfile
from app.domain.models.claim_evidence import EvidenceLink, MedicalClaim
from app.application.services.claim_evidence import ClaimEvidenceService
from app.application.services.evidence_coverage import EvidenceCoverageService
from app.application.services.discussion_transfer import DiscussionTransferService


from app.interfaces.storage.source_lifecycle_repository import SourceLifecycleRepository


class UserSessionRepository(SourceLifecycleRepository):
    """Small local SQLite store for workflow memory scoped by user and project."""

    def review_claim_evidence(
        self, user_id: str, project_id: str, expected_revision: int, slide_index: int,
        claims: list[MedicalClaim], link: EvidenceLink, actor: str,
    ) -> tuple[str, GraphState]:
        """Atomically persist claim evidence and its privacy-safe audit event."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT thread_id, state_json, revision FROM project_sessions WHERE user_id = ? AND project_id = ?",
                (user_id, project_id),
            ).fetchone()
            if row is None:
                raise WorkflowError("PROJECT_NOT_FOUND", "Project not found.")
            if type(expected_revision) is not int or row[2] != expected_revision:
                raise ConcurrentModificationError()
            state = self._deserialize_state(json.loads(row[1]))
            state.resource_library = self._load_resources(connection, user_id, project_id)
            state.project_revision = row[2]
            if state.presentation is None or not 0 <= slide_index < len(state.presentation.slides):
                raise WorkflowError("SLIDE_NOT_FOUND", "Slide not found.")
            slide = state.presentation.slides[slide_index]
            ClaimEvidenceService.set_claims(slide, claims)
            ClaimEvidenceService.review_link(slide, link, state.resource_library, actor)
            slide.is_validated = False
            state.presentation.state.slides_validated = False
            state.presentation.state.presentation_validated = False
            self._save_project_row(connection, user_id, project_id, row[0], state, None, claim_action=True)
            self._insert_event(connection, user_id, project_id, "CLAIM_EVIDENCE_REVIEWED", actor, {
                "slide_index": slide_index, "claim_id": link.claim_id,
                "claim_revision": link.claim_revision, "link_id": link.id,
                "link_revision": link.revision, "resource_id": link.resource_id,
                "location_kind": link.location_kind, "location_number": link.location_number,
                "provenance_verified": link.provenance_verified,
                "semantic_review": link.semantic_review,
            })
        return row[0], state

    def __init__(self, database_path: Path = Path("data/hpa.sqlite3")) -> None:
        self._resource_removal_token = object()
        self.database_path = database_path
        self.legacy_exports_path = Path("exports")
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
            columns = {row[1] for row in connection.execute("PRAGMA table_info(presentation_templates)")}
            if "prototype_declaration" not in columns:
                connection.execute("ALTER TABLE presentation_templates ADD COLUMN prototype_declaration TEXT")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(project_resources)")}
            if "original_pdf" not in columns:
                connection.execute("ALTER TABLE project_resources ADD COLUMN original_pdf BLOB")
            self._ensure_project_name_column(connection)
            self._ensure_project_revision_column(connection)
            self._ensure_user_profile_columns(connection)
            self._migrate_legacy_user_sessions(connection)
            self._recover_interrupted_jobs(connection)
            self._ensure_one_active_job_per_project(connection)
            self._init_source_lifecycle(connection)
        with self._connect() as connection:
            pending = connection.execute("SELECT pending FROM source_cleanup_state WHERE id = 1").fetchone()[0]
        if pending:
            self.finish_source_cleanup()

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

    def load_resource_chunks(
        self,
        user_id: str,
        project_id: str,
        resource_ids: Iterable[str] | None = None,
    ) -> list[ResourceChunk]:
        """Load retrieval passages directly from the normalized SQLite store."""
        selected_ids = tuple(resource_ids) if resource_ids is not None else None
        if selected_ids == ():
            return []
        with self._connect() as connection:
            return self._load_resource_chunks_connection(connection, user_id, project_id, selected_ids)

    def _load_resource_chunks_connection(self, connection, user_id, project_id, selected_ids=None):
        parameters: list[object] = [user_id, project_id]
        resource_filter = ""
        if selected_ids is not None:
            placeholders = ", ".join("?" for _ in selected_ids)
            resource_filter = f" AND chunks.resource_id IN ({placeholders})"
            parameters.extend(selected_ids)
        rows = connection.execute(
            f"""SELECT chunks.resource_id, chunks.page_number, chunks.chunk_position,
                       chunks.chunk_text, resources.metadata_json
                FROM project_resource_chunks AS chunks
                JOIN project_resources AS resources
                  ON resources.user_id = chunks.user_id
                 AND resources.project_id = chunks.project_id
                 AND resources.resource_id = chunks.resource_id
                WHERE chunks.user_id = ? AND chunks.project_id = ?{resource_filter}
                ORDER BY chunks.resource_id, chunks.page_number, chunks.chunk_position""",
            parameters,
        ).fetchall()
        chunks: list[ResourceChunk] = []
        for row in rows:
            try:
                metadata = json.loads(row[4])
            except (TypeError, json.JSONDecodeError):
                metadata = {}
            title = metadata.get("title") or metadata.get("filename") or row[0]
            chunks.append(
                ResourceChunk(
                    resource_id=row[0], page=row[1], position=row[2], text=row[3], title=title
                )
            )
        return chunks

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
        self._cleanup_if_pending()

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
        self._cleanup_if_pending()

    def _cleanup_if_pending(self):
        with self._connect() as connection:
            pending = connection.execute("SELECT pending FROM source_cleanup_state WHERE id = 1").fetchone()[0]
        if pending:
            self.finish_source_cleanup()

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

    def project_dashboard(self, user_id: str) -> dict[str, object]:
        """Return metadata-only cards for the authenticated user's Projects.

        This is read-only recovery data.  ``updated_at`` changes in the same
        SQLite transaction as persisted state and its audit event, so a failed
        save cannot be shown here as a successful save.
        """
        with self._connect() as connection:
            projects = connection.execute(
                """SELECT project_id, project_name, state_json, updated_at
                   FROM project_sessions WHERE user_id = ?
                   ORDER BY updated_at DESC, project_id ASC""",
                (user_id,),
            ).fetchall()
            events = connection.execute(
                """SELECT project_id, event_type, actor, created_at
                   FROM project_events WHERE user_id = ?
                   ORDER BY created_at DESC, rowid DESC""",
                (user_id,),
            ).fetchall()
            resources = connection.execute(
                """SELECT project_id, resource_id, metadata_json
                   FROM project_resources WHERE user_id = ?""",
                (user_id,),
            ).fetchall()
            templates = connection.execute(
                """SELECT resource_id, json_extract(resource_json, '$.filename') FROM owner_resources
                   WHERE user_id = ?""",
                (user_id,),
            ).fetchall()

        recent_by_project: dict[str, list[dict[str, str]]] = {}
        for project_id, event_type, actor, created_at in events:
            recent = recent_by_project.setdefault(project_id, [])
            if len(recent) < 5:
                recent.append({
                    "event_type": event_type,
                    "actor": actor,
                    "created_at": created_at,
                })
        resources_by_project: dict[str, dict[str, str]] = {}
        for project_id, resource_id, metadata_json in resources:
            metadata = json.loads(metadata_json)
            resources_by_project.setdefault(project_id, {})[resource_id] = str(
                metadata.get("file_type", "unknown")
            )
        template_names = {template_id: filename for template_id, filename in templates}

        cards: list[dict[str, object]] = []
        for project_id, project_name, state_json, updated_at in projects:
            state = self._deserialize_state(json.loads(state_json))
            presentation = state.presentation
            selected_ids = {resource.id for resource in presentation.resources} if presentation else set()
            type_counts: dict[str, int] = {}
            for resource_id in selected_ids:
                resource_type = resources_by_project.get(project_id, {}).get(resource_id, "unknown")
                type_counts[resource_type] = type_counts.get(resource_type, 0) + 1
            cards.append({
                "id": project_id,
                "name": project_name,
                "workflow_status": presentation.state.workflow_status.value if presentation else "context_collection",
                "context": presentation.context.model_dump(mode="json") if presentation else None,
                "theme": presentation.theme.value if presentation else None,
                "custom_template_name": (
                    template_names.get(presentation.custom_template_id)
                    if presentation and presentation.custom_template_id else None
                ),
                "resource_count": len(selected_ids),
                "resource_types": type_counts,
                "recent_actions": recent_by_project.get(project_id, []),
                "last_successful_save": updated_at,
            })
        return {"project_count": len(cards), "projects": cards}

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

    def delete_user(self, user_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for (project,) in connection.execute("SELECT project_id FROM project_sessions WHERE user_id = ?", (user_id,)).fetchall():
                self._delete_project_rows(connection, user_id, project)
            connection.execute("INSERT OR IGNORE INTO deletion_markers(user_id, kind, object_id) SELECT user_id, 'source', resource_id FROM owner_resources WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM owner_resources WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM source_deletion_audit WHERE user_id = ?", (user_id,))
            connection.execute("UPDATE source_cleanup_state SET pending = pending + 1 WHERE id = 1")
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
        self.finish_source_cleanup()
        for row in rows:
            (self.templates_path / row[0]).unlink(missing_ok=True)

    def save_presentation_template(self, user_id: str, filename: str, content: bytes, *, prototype_declaration: str | None = None) -> dict[str, str]:
        """Explicit import into the owner library, with the same source gates.

        Keep a reference to the canonical original, never a separate disk copy.
        Import does not select a style or approve any extraction.
        """
        PrototypePolicy.declaration(prototype_declaration)
        PrototypePolicy.screen(filename)
        if not filename.lower().endswith(".pptx"):
            raise SourceScreening.incomplete()
        resource = SourceDocument.read(filename, content, str(uuid4()))
        with self._connect() as connection:
            self._remember_source(connection, user_id, resource)
            connection.execute(
                """INSERT INTO presentation_templates (template_id, user_id, filename, stored_filename, prototype_declaration)
                   VALUES (?, ?, ?, ?, ?)""",
                (resource.id, user_id, resource.filename, "source:" + resource.id, prototype_declaration),
            )
            self._insert_event(connection, user_id, "", "GRAPHIC_SOURCE_IMPORTED", user_id,
                               {"resource_id": resource.id, "original_sha256": resource.metadata.original_sha256, "workflow_stage": "library_import"})
        return {"id": resource.id, "filename": resource.filename}

    def list_presentation_templates(self, user_id: str) -> list[dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT t.template_id, t.filename FROM presentation_templates t
                   JOIN owner_resources r ON r.user_id = t.user_id AND r.resource_id = t.template_id
                   WHERE t.user_id = ? AND t.stored_filename = 'source:' || t.template_id
                   ORDER BY t.created_at DESC""", (user_id,),
            ).fetchall()
        return [{"id": row[0], "filename": row[1]} for row in rows]

    def presentation_template_source(self, user_id: str, template_id: str) -> Resource | None:
        """Return the verified original for explicit graphic reuse."""
        with self._connect() as connection:
            registration = connection.execute("SELECT prototype_declaration FROM presentation_templates WHERE user_id = ? AND template_id = ?", (user_id, template_id)).fetchone()
        if registration and registration[0] not in ("public", "synthetic"):
            return None
        resource = self.library_resource(user_id, template_id)
        if resource is None or resource.file_type.value != "pptx" or resource._original_content is None:
            return None
        SourceDocument.verify(resource, resource._original_content)
        return resource

    def select_presentation_style(self, user, project, expected_revision, *, template_id=None, theme=None):
        """Authenticated API supplies the owner; state, invalidation and audit commit together."""
        from app.application.services.source_date_policy import SourceDatePolicy
        stored = self.load(user, project)
        if stored is None:
            raise WorkflowError("PROJECT_NOT_FOUND", "Project not found.")
        thread, state = stored
        PrototypePolicy.declaration(state.prototype_declaration)
        if type(expected_revision) is not int or state.project_revision != expected_revision:
            raise ConcurrentModificationError()
        presentation = state.presentation
        if presentation is None:
            raise WorkflowError("PRESENTATION_REQUIRED", "Create a presentation before selecting a style.")
        if template_id:
            if not presentation.state.blueprint_validated:
                raise WorkflowError("BLUEPRINT_APPROVAL_REQUIRED", "Approve the Blueprint before reusing a graphic template.")
            source = self.presentation_template_source(user, template_id)
            if source is None or source.file_type.value != "pptx" or source._original_content is None:
                raise WorkflowError("TEMPLATE_UNAVAILABLE", "Select a screened PowerPoint from your local library.")
            SourceDocument.verify(source, source._original_content)
            SourceDatePolicy.require(source, allow_unconfirmed=True)
            presentation.custom_template_id = source.id
        elif theme is not None:
            presentation.theme = theme
            presentation.custom_template_id = None
        else:
            raise WorkflowError("STYLE_REQUIRED", "Select a built-in theme or a screened PowerPoint.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM project_jobs WHERE user_id = ? AND project_id = ? AND status IN ('queued', 'running')", (user, project)).fetchone():
                raise ProjectJobRunningError()
            self._save_project_row(connection, user, project, thread, state, None, style_action=True)
            self._insert_event(connection, user, project, "PRESENTATION_THEME_SELECTED", user,
                               {"template_resource_id": presentation.custom_template_id, "theme": presentation.theme.value,
                                "workflow_status": presentation.state.workflow_status.value,
                                "original_sha256": source.metadata.original_sha256 if template_id else None})
        self._cleanup_if_pending()
        return thread, state

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
        """Create the only state-writing job permitted for one Project."""
        job_id = str(uuid4())
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                self._assert_not_deleted(connection, user_id, "project", project_id)
                connection.execute(
                    """INSERT INTO project_jobs (job_id, user_id, project_id, domain, status, progress, stage)
                       VALUES (?, ?, ?, ?, 'queued', 0, 'queued')""",
                    (job_id, user_id, project_id, domain),
                )
        except sqlite3.IntegrityError as exc:
            raise ProjectJobRunningError() from exc
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
                   WHERE job_id = ? AND user_id = ? AND status != 'cancelled'""",
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

    def active_job(self, user_id: str, project_id: str) -> dict[str, object] | None:
        """Return the one durable state-writing job currently running for a Project."""
        with self._connect() as connection:
            row = connection.execute(
                """SELECT job_id FROM project_jobs
                   WHERE user_id = ? AND project_id = ? AND status IN ('queued', 'running')
                   ORDER BY created_at DESC LIMIT 1""",
                (user_id, project_id),
            ).fetchone()
        return self.get_job(user_id, row[0]) if row else None

    @staticmethod
    def _serialize_state(state: GraphState) -> dict[str, object]:
        # Resource documents/pages are persisted in dedicated tables. Keeping
        # them out of this state snapshot prevents every chat turn from
        # rewriting all extracted PDF content.
        payload = state.model_dump(mode="json", exclude={"messages", "resource_library", "resource_chunks"})
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
    def _ensure_one_active_job_per_project(connection: sqlite3.Connection) -> None:
        """Atomically prevent concurrent jobs from racing to save one Project."""
        connection.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS idx_project_jobs_one_active_per_project
               ON project_jobs (user_id, project_id)
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
        connection.execute("PRAGMA secure_delete = ON")
        return connection

    def _save_project_row(
        self,
        connection: sqlite3.Connection,
        user_id: str,
        project_id: str,
        thread_id: str,
        state: GraphState,
        project_name: str | None,
        *, style_action: bool = False, claim_action: bool = False, coverage_action: bool = False,
        transfer_action: bool = False,
    ) -> None:
        if not connection.in_transaction:
            connection.execute("BEGIN IMMEDIATE")
        self._assert_not_deleted(connection, user_id, "project", project_id)
        # Check both copies before normalization can discard a malicious selection.
        for resource in state.resource_library:
            self._assert_not_deleted(connection, user_id, "source", resource.id)
            SourceScreening.resource(resource, require_text=True)
        for resource in state.presentation.resources if state.presentation else []:
            self._assert_not_deleted(connection, user_id, "source", resource.id)
            SourceScreening.resource(resource)
        # PPTX selections are references to canonical owner-library evidence,
        # never an alternate place to persist caller-supplied asset descriptors.
        for selected in state.presentation.resources if state.presentation else []:
            if selected.file_type.value == "pptx" or selected.metadata.origin == "pptx_memory_import" or selected.metadata.assets:
                canonical = next((source for source in state.resource_library if source.id == selected.id), None)
                if canonical is not None:
                    if resource_selection(selected) != resource_selection(canonical):
                        raise WorkflowError("SOURCE_INTEGRITY_FAILED", "Selected source metadata differs from its verified library original.")
                elif not selected.extracted_pages:
                    raise WorkflowError("SOURCE_ORIGINAL_REQUIRED", "Select a verified library source before saving.")
        ensure_resource_library(state)
        if state.presentation:
            for slide in state.presentation.slides:
                claims = {(claim.id, claim.revision) for claim in slide.claims}
                for link in slide.evidence_links:
                    if ((link.claim_id, link.claim_revision) not in claims
                            and (link.provenance_verified or link.semantic_review != "pending")):
                        raise WorkflowError("CLAIM_EVIDENCE_INVALID", "Evidence link targets an unknown claim revision.")
                    if link.provenance_verified or link.semantic_review != "pending":
                        ClaimEvidenceService.verify_provenance(link, state.resource_library)
                    if link.semantic_review != "pending" and not link.semantic_reviewed_by:
                        raise WorkflowError("CLAIM_EVIDENCE_INVALID", "Semantic review has no authenticated reviewer.")
                ClaimEvidenceService._refresh(slide)
                note = slide.speaker_note
                if note is not None:
                    note_claims = {(claim.id, claim.revision) for claim in note.claims}
                    for link in note.evidence_links:
                        if (link.claim_id, link.claim_revision) not in note_claims:
                            raise WorkflowError(
                                "SPEAKER_NOTE_EVIDENCE_INVALID",
                                "Speaker-note evidence targets an unknown claim revision.",
                            )
                        if link.provenance_verified or link.semantic_review != "pending":
                            ClaimEvidenceService.verify_provenance(link, state.resource_library)
                    if note.is_approved or note.approved_by:
                        raise WorkflowError(
                            "EXPLICIT_SPEAKER_NOTE_REVIEW_REQUIRED",
                            "Use the authenticated speaker-note review action.",
                        )
        existing = connection.execute(
            "SELECT revision FROM project_sessions WHERE user_id = ? AND project_id = ?",
            (user_id, project_id),
        ).fetchone()
        current_revision = existing[0] if existing else None
        if current_revision is not None and state.project_revision != current_revision:
            raise ConcurrentModificationError()

        next_revision = 1 if current_revision is None else current_revision + 1
        old_resources = []
        previous_row = connection.execute("SELECT state_json FROM project_sessions WHERE user_id = ? AND project_id = ?", (user_id, project_id)).fetchone()
        if previous_row:
            previous = self._deserialize_state(json.loads(previous_row[0]))
            if not claim_action and state.presentation and previous.presentation:
                old_approved = {
                    (link.id, link.revision, link.claim_id, link.claim_revision)
                    for slide in previous.presentation.slides for link in slide.evidence_links
                    if link.semantic_review == "approved" and link.provenance_verified
                }
                new_approved = {
                    (link.id, link.revision, link.claim_id, link.claim_revision)
                    for slide in state.presentation.slides for link in slide.evidence_links
                    if link.semantic_review == "approved" and link.provenance_verified
                }
                if new_approved - old_approved:
                    raise WorkflowError("EXPLICIT_CLAIM_REVIEW_REQUIRED", "Use the authenticated claim-evidence review action.")
            old_resources = self._load_resources(connection, user_id, project_id) or previous.resource_library
            removed = {r.id for r in old_resources} - {r.id for r in state.resource_library}
            old_selected = {r.id for r in previous.presentation.resources} if previous.presentation else set()
            selected = {r.id for r in state.presentation.resources} if state.presentation else set()
            if removed or old_selected - selected:
                self._invalidate_project_storage(connection, user_id, project_id, state)
        old_presentation = previous.presentation if previous_row else None
        old_transfer = previous.planning_transfer if previous_row else None
        if not transfer_action and state.planning_transfer != old_transfer:
            raise WorkflowError("EXPLICIT_DISCUSSION_TRANSFER_REQUIRED", "Use the authenticated discussion-transfer action.")
        if not transfer_action and state.planning_transfer is not None:
            state.resource_chunks = self._load_resource_chunks_connection(connection, user_id, project_id)
            if not DiscussionTransferService().is_current(state.planning_transfer, state):
                state.planning_transfer.status = "obsolete"
        presentation = state.presentation
        if presentation:
            old_coverage = old_presentation.evidence_coverage if old_presentation else None
            if not coverage_action and presentation.evidence_coverage != old_coverage:
                raise WorkflowError("EXPLICIT_COVERAGE_ASSESSMENT_REQUIRED", "Use the authenticated evidence-coverage assessment action.")
            if not coverage_action and presentation.evidence_coverage is not None:
                selected_resources = [r for r in state.resource_library if r.id in {s.id for s in presentation.resources}]
                current_chunks = self._load_resource_chunks_connection(connection, user_id, project_id)
                if not EvidenceCoverageService().is_current(
                    presentation.evidence_coverage, presentation, selected_resources, current_chunks
                ):
                    presentation.evidence_coverage = None
            old_template = old_presentation.custom_template_id if old_presentation else None
            # Detaching the original removes its graphic use as well.
            removed_template = old_template and (
                (old_template in {r.id for r in old_resources} and old_template not in {r.id for r in state.resource_library})
                or connection.execute("SELECT 1 FROM deletion_markers WHERE user_id = ? AND kind = 'source' AND object_id = ?", (user_id, old_template)).fetchone()
            )
            if removed_template and presentation.custom_template_id == old_template:
                presentation.custom_template_id = None
            changed_template = presentation.custom_template_id != old_template
            changed_theme = old_presentation and presentation.theme != old_presentation.theme
            automatic_clear = removed_template and presentation.custom_template_id is None and not changed_theme
            if (changed_template or changed_theme) and not style_action and not automatic_clear:
                raise WorkflowError("EXPLICIT_STYLE_ACTION_REQUIRED", "Use the explicit style-selection action.")
            if presentation.custom_template_id:
                self._assert_not_deleted(connection, user_id, "source", presentation.custom_template_id)
                candidate = connection.execute("SELECT resource_json FROM owner_resources WHERE user_id = ? AND resource_id = ?", (user_id, presentation.custom_template_id)).fetchone()
                if candidate is None or json.loads(candidate[0]).get("file_type") != "pptx":
                    raise WorkflowError("TEMPLATE_UNAVAILABLE", "Select a screened PowerPoint from your local library.")
            if changed_template or changed_theme:
                self._queue_project_exports(connection, user_id, project_id, state)
                presentation.state.presentation_validated = False
                presentation.state.slides_validated = False
                for slide in presentation.slides:
                    slide.is_validated = False
                if presentation.slides:
                    from app.domain.enums.workflow_status import WorkflowStatus
                    presentation.state.workflow_status = WorkflowStatus.AWAITING_SLIDE_APPROVAL
        self._sync_resources(connection, user_id, project_id, state.resource_library, _removal_token=self._resource_removal_token)
        for resource in old_resources:
            present = connection.execute("SELECT 1 FROM owner_resources WHERE user_id = ? AND resource_id = ?", (user_id, resource.id)).fetchone()
            deleted = connection.execute("SELECT 1 FROM deletion_markers WHERE user_id = ? AND kind = 'source' AND object_id = ?", (user_id, resource.id)).fetchone()
            if not present and not deleted:
                self._remember_source(connection, user_id, resource)
        state.project_revision = next_revision
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
        self, connection: sqlite3.Connection, user_id: str, project_id: str, resources: list[Resource], *, _removal_token=None
    ) -> None:
        if not connection.in_transaction:
            connection.execute("BEGIN IMMEDIATE")
        self._assert_not_deleted(connection, user_id, "project", project_id)
        # All checks precede even DELETEs; private repository calls cannot skip them.
        for resource in resources:
            self._assert_not_deleted(connection, user_id, "source", resource.id)
            SourceScreening.resource(resource, require_text=True)
        # Verify the whole batch before any mutation, including removals.
        originals = {}
        stored_resources = {item.id: item for item in self._load_resources(connection, user_id, project_id)}
        row = connection.execute(
            "SELECT state_json FROM project_sessions WHERE user_id = ? AND project_id = ?", (user_id, project_id)
        ).fetchone()
        if row:
            for item in self._deserialize_state(json.loads(row[0])).resource_library:
                stored_resources.setdefault(item.id, item)
        for resource in resources:
            previous = stored_resources.get(resource.id)
            content = resource._original_content or (previous._original_content if previous else None)
            if content is not None:
                if previous is not None and content != previous._original_content:
                    raise WorkflowError("SOURCE_REPLACEMENT_REQUIRED", "Import a replacement under a new resource ID; an existing source original cannot be overwritten.")
                unchanged = (previous is not None and previous._original_content == content
                             and resource.model_dump(mode="json") == previous.model_dump(mode="json")
                             and hashlib.sha256(content).hexdigest() == resource.metadata.original_sha256)
                originals[resource.id] = content if unchanged else SourceDocument.verify(resource, content)
                resource._original_content = content
            elif previous is None or resource.model_dump(mode="json", exclude={"uploaded_at", "extracted_text"}) != previous.model_dump(mode="json", exclude={"uploaded_at", "extracted_text"}):
                raise WorkflowError("SOURCE_ORIGINAL_REQUIRED", "The original PDF is missing. Replace this source by importing its dated original.")
            else:
                # Unchanged historical records can still be saved/read/removed;
                # their absence of reliable dates blocks scientific use separately.
                originals[resource.id] = None
        existing = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT resource_id, content_hash FROM project_resources WHERE user_id = ? AND project_id = ?",
                (user_id, project_id),
            )
        }
        incoming_ids = {resource.id for resource in resources}
        removed_ids = set(existing).difference(incoming_ids)
        if removed_ids and _removal_token is not self._resource_removal_token:
            raise WorkflowError("SOURCE_REMOVAL_REQUIRES_STATE", "Remove the source through a Project state transaction.")
        for resource in resources:
            self._remember_source(
                connection, user_id, resource, check_only=True,
                _verification_token=self._source_verification_token,
            )
        for resource in resources:
            self._remember_source(
                connection, user_id, resource,
                _verification_token=self._source_verification_token,
            )
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
                """INSERT INTO project_resources (user_id, project_id, resource_id, metadata_json, content_hash, original_pdf)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, project_id, resource_id) DO UPDATE SET
                   metadata_json = excluded.metadata_json, content_hash = excluded.content_hash,
                   original_pdf = excluded.original_pdf,
                   updated_at = CURRENT_TIMESTAMP""",
                (user_id, project_id, resource.id, json.dumps(metadata), content_hash, originals[resource.id]),
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
            chunks = self._chunks_for_pages(pages)
            connection.executemany(
                """INSERT INTO project_resource_chunks
                   (user_id, project_id, resource_id, page_number, chunk_position, chunk_text)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (user_id, project_id, resource.id, page, position, text)
                    for page, position, text in chunks
                ],
            )

    @staticmethod
    def _load_resources(connection: sqlite3.Connection, user_id: str, project_id: str) -> list[Resource]:
        rows = connection.execute(
            """SELECT resource_id, metadata_json, original_pdf FROM project_resources
               WHERE user_id = ? AND project_id = ? ORDER BY updated_at, resource_id""",
            (user_id, project_id),
        ).fetchall()
        resources: list[Resource] = []
        for resource_id, metadata_json, original_pdf in rows:
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
            resources[-1]._original_content = original_pdf
            if resources[-1].metadata.ocr_reviews or resources[-1].metadata.asset_reviews:
                try:
                    SourceLifecycleRepository._verify_review_authority(connection, user_id, resources[-1])
                except WorkflowError:
                    pass  # Readable recovery state, never trusted for generation.
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
        SourceLifecycleRepository._assert_not_deleted(connection, user_id, "project", project_id)
        connection.execute(
            """INSERT INTO project_events
               (event_id, user_id, project_id, event_type, actor, payload_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                str(uuid4()), user_id, project_id, event_type, actor,
                json.dumps(payload or {}, default=str),
            ),
        )

    def assess_evidence_coverage(
        self, user_id: str, project_id: str, expected_revision: int, actor: str
    ) -> tuple[str, GraphState]:
        """Atomically calculate, persist and audit the server-owned FR-09 decision."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT thread_id, state_json, revision FROM project_sessions WHERE user_id = ? AND project_id = ?",
                (user_id, project_id),
            ).fetchone()
            if row is None:
                raise WorkflowError("PROJECT_NOT_FOUND", "Project not found.")
            if type(expected_revision) is not int or row[2] != expected_revision:
                raise ConcurrentModificationError()
            state = self._deserialize_state(json.loads(row[1]))
            state.resource_library = self._load_resources(connection, user_id, project_id)
            state.resource_chunks = self._load_resource_chunks_connection(connection, user_id, project_id)
            state.project_revision = row[2]
            if state.presentation is None:
                raise WorkflowError("PRESENTATION_NOT_CREATED", "Create a presentation before assessing evidence coverage.")
            if not state.presentation.state.resources_validated:
                raise WorkflowError("RESOURCES_NOT_VALIDATED", "Validate the selected resources before assessing coverage.")
            resources = [r for r in state.resource_library if r.id in {s.id for s in state.presentation.resources}]
            assessment = EvidenceCoverageService().assess(state.presentation, resources, state.resource_chunks)
            state.presentation.evidence_coverage = assessment
            self._save_project_row(connection, user_id, project_id, row[0], state, None, coverage_action=True)
            self._insert_event(connection, user_id, project_id, "EVIDENCE_COVERAGE_ASSESSED", actor, {
                "coverage_version": assessment.version,
                "sufficient": assessment.sufficient,
                "dimensions": [{"dimension": r.dimension, "sufficient": r.sufficient,
                                "passage_count": len(r.passages)} for r in assessment.results],
            })
        return row[0], state

    def approve_discussion_transfer(
        self, user_id: str, project_id: str, expected_revision: int, destination: str,
        content: str, retained_position_ids: list[str], uncertainties: list[str], actor: str,
    ) -> tuple[str, GraphState]:
        """Atomically validate, persist and audit explicit human planning input."""
        if actor != user_id or actor.casefold() in {"model", "llm", "system"}:
            raise WorkflowError("HUMAN_TRANSFER_APPROVAL_REQUIRED", "An authenticated Project owner must approve the transfer.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT thread_id, state_json, revision FROM project_sessions WHERE user_id = ? AND project_id = ?",
                (user_id, project_id),
            ).fetchone()
            if row is None:
                raise WorkflowError("PROJECT_NOT_FOUND", "Project not found.")
            if type(expected_revision) is not int or row[2] != expected_revision:
                raise ConcurrentModificationError()
            state = self._deserialize_state(json.loads(row[1]))
            state.resource_library = self._load_resources(connection, user_id, project_id)
            state.resource_chunks = self._load_resource_chunks_connection(connection, user_id, project_id)
            state.project_revision = row[2]
            transfer = DiscussionTransferService().create_transfer(
                state, destination, content, retained_position_ids, uncertainties, actor
            )
            old = state.planning_transfer
            transfer.revision = old.revision + 1 if old else 1
            state.planning_transfer = transfer
            self._save_project_row(connection, user_id, project_id, row[0], state, None, transfer_action=True)
            self._insert_event(connection, user_id, project_id, "DISCUSSION_TRANSFER_APPROVED", actor, {
                "transfer_revision": transfer.revision, "destination": transfer.destination,
                "position_count": len(transfer.positions), "uncertainty_count": len(transfer.uncertainties),
                "conflicts_retained": len(transfer.retained_position_ids), "status": transfer.status,
            })
        return row[0], state
