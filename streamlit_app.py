"""Streamlit user interface for the Healthcare Presentation Assistant."""
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import streamlit as st
from langchain_core.messages import HumanMessage

from app.ai.agents.healthcare_presentation_agent import HealthcarePresentationAgent
from app.ai.workflows.graph_state import GraphState
from app.application.use_cases.export_powerpoint import ExportPowerPointUseCase
from app.application.use_cases.extract_pdf_resource import ExtractPdfResourceUseCase
from app.application.use_cases.summarize_resources import SummarizeResourcesUseCase
from app.application.use_cases.discuss_resources import DiscussResourcesUseCase
from app.application.use_cases.update_presentation_details import UpdatePresentationDetailsUseCase
from app.application.use_cases.update_project_evidence_settings import UpdateProjectEvidenceSettingsUseCase
from app.application.use_cases.manage_project_resources import (
    AddProjectResourceUseCase,
    AttachResourceToPresentationUseCase,
    DetachResourceFromPresentationUseCase,
    RemoveProjectResourceUseCase,
)
from app.application.use_cases.workflow_steps import (
    BuildBlueprintWorkflowUseCase,
    CollectPresentationContextUseCase,
    CreatePresentationWorkflowUseCase,
    RejectBlueprintItemUseCase,
    RejectSlideUseCase,
    EditBlueprintItemUseCase,
    EditSlideUseCase,
    AuthorSlideFromBlueprintUseCase,
    RegenerateBlueprintUseCase,
    RegenerateSlideUseCase,
    RecordProfessionalScopeUseCase,
    ReviewBlueprintItemUseCase,
    ReviewSlideUseCase,
    GenerateSlidesWorkflowUseCase,
    ValidatePresentationContextUseCase,
)
from app.ai.workflows.tools import (
    validate_final_presentation,
    validate_resources,
)
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.domain.models.user_profile import UserProfile
from app.domain.enums.presentation_theme import PresentationTheme
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.enums.evidence_context_mode import EvidenceContextMode
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.models.execution_context import ExecutionContext
from app.application.services.conversation_history import (
    add_resource_turn,
    add_turn,
    ensure_history,
    message_text as transcript_message_text,
)
from app.application.services.resource_library import ensure_resource_library, resolve_presentation_resources
from app.application.services.workflow_policy import WorkflowPolicy
from app.application.services.citation_presentation import (
    citation_display_details,
    format_citations_for_display,
)
from app.domain.exceptions.domain_error import DomainError
from app.domain.exceptions.project_job_running_error import ProjectJobRunningError
from app.interfaces.api.job_runner import submit as submit_job


st.set_page_config(page_title="Healthcare Presentation Assistant", page_icon="🩺", layout="wide")


ROLE_OPTIONS = [
    "professor_medicine",
    "assistant_professor",
    "veterinarian",
    "biologist",
    "pharmacist",
    "specialist_physician",
    "resident_physician",
]


def role_label(role: str) -> str:
    return {
        "professor_medicine": "Professor of Medicine",
        "assistant_professor": "Assistant Professor",
        "veterinarian": "Veterinarian",
        "biologist": "Biologist",
        "pharmacist": "Pharmacist",
        "specialist_physician": "Specialist Physician",
        "resident_physician": "Resident Physician",
    }.get(role, role.replace("_", " ").title())


def role_emblem(role: str) -> str:
    """Return the same clear professional emblems used by the web application."""
    asclepius = """<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3v26M12 6c-5 1-5 7-1 8 6 1 6-6 1-4-4 2-1 8 4 8 5 0 7-6 3-10-2-2-5-2-7-1"/><path d="M12 3h8"/></svg>"""
    emblems = {
        "professor_medicine": asclepius,
        "assistant_professor": asclepius,
        "specialist_physician": asclepius,
        "resident_physician": asclepius,
        # Veterinary medicine: a recognisable V combined with the Rod of Asclepius.
        "veterinarian": """<svg viewBox="0 0 40 32" aria-hidden="true"><path d="M3 4 12 28 21 4"/><path d="M28 3v26M25 7c-4 1-4 6-1 7 5 1 5-5 1-4-3 1-1 6 3 6 4 0 6-5 3-8-2-2-5-2-6-1"/><path d="M24 3h8"/></svg>""",
        "biologist": """<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M8 4c12 7 4 17 16 24M24 4C12 11 20 21 8 28M10 8h12M8 16h16M10 24h12"/></svg>""",
        "pharmacist": """<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M6 20h20M9 20c1 6 13 6 14 0M12 25h8M17 5c7-2 9 6 4 8-5 2-7-4-3-6 3-2 6 3 2 6-3 3-8 0-8-4"/><path d="M13 14h8l-2 6h-4z"/></svg>""",
    }
    return emblems.get(role, asclepius)


def _preview_label(presentation, english: str, french: str, arabic: str) -> str:
    """Choose the same display language used by the exported PowerPoint."""
    language = presentation.context.language.value
    return french if language == "French" else arabic if language == "Arabic" else english


def _presentation_preview_pages(presentation, resources) -> list[dict[str, object]]:
    """Build local preview pages from the exact content passed to the exporter."""
    if not presentation.slides:
        return []
    context = presentation.context
    presenter = " · ".join(value for value in (context.presenter_name, context.presenter_title) if value)
    location = " · ".join(value for value in (context.venue, context.presentation_date) if value)
    details = [value for value in (presenter, context.organization, context.event_name, location) if value]
    pages: list[dict[str, object]] = [
        {
            "kind": "cover",
            "title": presentation.title,
            "objective": context.objective,
            "details": details,
            "meta": f"{context.duration_minutes} min · {context.audience.value}",
        }
    ]
    if presentation.agenda and presentation.agenda.items:
        pages.append(
            {
                "kind": "agenda",
                "title": _preview_label(presentation, "Agenda", "Agenda", "جدول الأعمال"),
                "items": list(presentation.agenda.items),
            }
        )
    for slide in presentation.slides:
        pages.append(
            {
                "kind": "content",
                "title": slide.title,
                "items": list(slide.key_messages or [slide.content]),
                "origin": slide.content_origin,
                "references": list(slide.reference_details)
                if slide.content_origin == "ai_generated" and slide.evidence_verified
                else [],
            }
        )
    batches = [resources[index:index + 4] for index in range(0, len(resources), 4)]
    origins = {
        "ai_generated": sum(slide.content_origin == "ai_generated" for slide in presentation.slides),
        "user_edited": sum(slide.content_origin == "user_edited" for slide in presentation.slides),
        "user_authored": sum(slide.content_origin == "user_authored" for slide in presentation.slides),
    }
    for number, batch in enumerate(batches, start=1):
        pages.append(
            {
                "kind": "resources",
                "title": _preview_label(
                    presentation,
                    "Resources and validation",
                    "Ressources et validation",
                    "المصادر والاعتماد",
                ),
                "resources": batch,
                "batch": number,
                "batches": len(batches),
                "origins": origins,
            }
        )
    return pages


def _preview_origin_label(origin: str) -> str:
    return {
        "ai_generated": "AI-generated",
        "user_edited": "User-edited",
        "user_authored": "User-authored",
    }.get(origin, "AI-generated")


def render_presentation_preview(presentation, resources, project_id: str) -> None:
    """Render a navigable, no-model preview before final PowerPoint download."""
    pages = _presentation_preview_pages(presentation, resources)
    if not pages:
        return
    palettes = {
        PresentationTheme.CLINICAL: ("#105968", "#31a199", "#f5fafa"),
        PresentationTheme.ACADEMIC: ("#1e3762", "#c2913e", "#f8f8fc"),
        PresentationTheme.EXECUTIVE: ("#242c3d", "#d1714b", "#faf9f7"),
        PresentationTheme.MIDNIGHT: ("#0f172a", "#38bdf8", "#f1f5f9"),
    }
    primary, accent, paper = palettes[presentation.theme]
    key = f"presentation_preview_index_{project_id}"
    index = min(max(int(st.session_state.get(key, 0)), 0), len(pages) - 1)
    st.session_state[key] = index
    page = pages[index]

    st.divider()
    st.subheader("Presentation preview")
    st.caption(
        "Local pre-export preview of the exact slide content, agenda and resources. "
        "It never calls the model."
    )
    if presentation.custom_template_id:
        st.info(
            "Your uploaded PowerPoint template is applied during export. This local preview shows "
            "the selected HPA theme and the exported content."
        )
    previous, counter, next_page = st.columns([1, 2, 1])
    if previous.button("← Previous", disabled=index == 0, key=f"preview_previous_{project_id}"):
        st.session_state[key] = index - 1
        st.rerun()
    counter.markdown(f"**Slide {index + 1} / {len(pages)}**")
    if next_page.button("Next →", disabled=index == len(pages) - 1, key=f"preview_next_{project_id}"):
        st.session_state[key] = index + 1
        st.rerun()

    with st.container(border=True):
        is_cover = page["kind"] == "cover"
        background = primary if is_cover else paper
        foreground = "#ffffff" if is_cover else primary
        st.markdown(
            f"<div style=\"border-left: 7px solid {accent}; background: {background}; color: {foreground}; "
            "padding: 0.75rem 1rem; border-radius: 0.4rem; font-weight: 700;\">"
            f"{escape(str(page['title']))}</div>",
            unsafe_allow_html=True,
        )
        if page["kind"] == "cover":
            st.write(str(page["objective"]))
            for detail in page["details"]:
                st.caption(str(detail))
            st.caption(str(page["meta"]))
        elif page["kind"] == "agenda":
            for position, item in enumerate(page["items"], start=1):
                st.write(f"{position}. {item}")
        elif page["kind"] == "content":
            for item in page["items"]:
                if item:
                    st.write(f"• {item}")
            references = page["references"]
            if references:
                st.caption("Verified evidence")
                for reference in references:
                    st.caption(
                        f"{reference.get('title', 'Source')} · p. {reference.get('page')} · "
                        f"{reference.get('resource_id')}"
                    )
            else:
                st.caption(f"{_preview_origin_label(str(page['origin']))} · Human-reviewed")
        else:
            if page["batch"] == 1:
                st.write("All listed resources were validated by the user.")
                origins = page["origins"]
                st.caption(
                    "Content provenance: "
                    f"{origins['ai_generated']} AI-generated, {origins['user_edited']} user-edited, "
                    f"{origins['user_authored']} user-authored."
                )
            for resource in page["resources"]:
                st.write(resource.title or resource.filename)
                if resource.source:
                    st.caption(resource.source)
                st.caption(f"Audit ID: {resource.id}")


@st.cache_resource
def get_agent() -> HealthcarePresentationAgent:
    return HealthcarePresentationAgent()


@st.cache_resource
def get_repository() -> UserSessionRepository:
    return UserSessionRepository()


def authenticated_user_id() -> str:
    """Use OIDC identity when configured, otherwise require a local password."""
    auth_required = bool(st.secrets.get("AUTH_REQUIRED", False))
    if auth_required:
        if not st.user.is_logged_in:
            st.title("Healthcare Presentation Assistant")
            st.button("Sign in with Google", on_click=st.login)
            st.stop()
        return str(st.user.get("sub") or st.user.get("email"))

    if local_user_id := st.session_state.get("local_authenticated_user_id"):
        return str(local_user_id)

    st.caption("Local sign in")
    with st.form("local_login"):
        user_id = st.text_input("User ID", max_chars=128).strip()
        password = st.text_input("Password", type="password", max_chars=256)
        login, register = st.columns(2)
        login_clicked = login.form_submit_button("Sign in")
        register_clicked = register.form_submit_button("Create account")
    if login_clicked:
        if get_repository().authenticate_user(user_id, password):
            st.session_state.local_authenticated_user_id = user_id
            st.rerun()
        st.error("Invalid user ID or password.")
    if register_clicked:
        try:
            if len(password) < 8:
                raise ValueError("Password must contain at least 8 characters.")
            get_repository().register_user(user_id, password)
            st.session_state.local_authenticated_user_id = user_id
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    st.stop()


def load_project_state(user_id: str, project_id: str) -> GraphState:
    """Load an isolated workflow state for one user project."""
    if (
        st.session_state.get("active_user_id") != user_id
        or st.session_state.get("active_project_id") != project_id
    ):
        stored = get_repository().load(user_id, project_id)
        thread_id, state = stored if stored else get_repository().create_empty(user_id, project_id)
        st.session_state.active_user_id = user_id
        st.session_state.active_project_id = project_id
        st.session_state.thread_id = thread_id
        st.session_state.state = state
        if ensure_resource_library(state):
            get_repository().save_with_event(
                user_id, project_id, thread_id, state,
                "PROJECT_STATE_MIGRATED", "system", {"reason": "resource_library_normalization"},
            )
        st.session_state.pop("pptx_data", None)
        st.session_state.pop("pptx_name", None)
    st.session_state.state.resource_chunks = get_repository().load_resource_chunks(user_id, project_id)
    return st.session_state.state


def save_state(
    event_type: str = "PROJECT_STATE_SAVED",
    actor: str = "user",
    payload: dict[str, object] | None = None,
) -> None:
    """Persist the active Project and its audit event in one SQLite transaction."""
    get_repository().save_with_event(
        st.session_state.active_user_id,
        st.session_state.active_project_id,
        st.session_state.thread_id,
        st.session_state.state,
        event_type,
        actor,
        payload or {},
    )


def _load_current_project_for_job(repository: UserSessionRepository, user_id: str, project_id: str) -> tuple[str, GraphState]:
    """Reload the durable state inside a worker instead of trusting a stale UI copy."""
    stored = repository.load(user_id, project_id)
    if stored is None:
        raise ValueError("Project not found.")
    thread_id, current_state = stored
    current_state.resource_chunks = repository.load_resource_chunks(user_id, project_id)
    current_state.user_profile = repository.get_user_profile(user_id)
    if current_state.presentation is not None:
        current_state.presentation.owner_profile = current_state.user_profile
    return thread_id, current_state


def _job_error_details(exc: Exception) -> tuple[str, str, bool]:
    """Keep durable job errors actionable without storing provider internals in the Project state."""
    if isinstance(exc, DomainError):
        return exc.code, exc.user_message, exc.retryable
    if isinstance(exc, ValueError):
        return "WORKFLOW_VALIDATION_FAILED", str(exc), False
    return "LLM_PROVIDER_FAILURE", "The model could not complete this request. Please retry.", True


def _persist_streamlit_job_failure(
    repository: UserSessionRepository,
    user_id: str,
    project_id: str,
    thread_id: str,
    current_state: GraphState,
    operation: str,
    exc: Exception,
    failure_event: str = "WORKFLOW_GENERATION_FAILED",
) -> ValueError:
    """Record a safe, durable failure for every asynchronous Streamlit model operation."""
    code, message, retryable = _job_error_details(exc)
    current_state.execution = ExecutionContext(
        last_tool=operation,
        tool_output={"status": "failed", "error_code": code, "retryable": retryable},
        error=message,
    )
    repository.save_with_event(
        user_id,
        project_id,
        thread_id,
        current_state,
        failure_event,
        "system",
        {"operation": operation, "error_code": code, "retryable": retryable},
    )
    return ValueError(message)


def _project_job_is_running() -> bool:
    """Prevent a Streamlit callback from mutating a Project while a job owns it."""
    active = get_repository().active_job(
        st.session_state.active_user_id,
        st.session_state.active_project_id,
    )
    if active is None:
        return False
    st.error("A workflow job is already running for this Project. Wait for it to finish before continuing.")
    return True


def _queue_streamlit_job(
    domain: str,
    operation: str,
    work,
) -> bool:
    """Schedule one state-writing Project job using the same SQLite lock as the web app."""
    user_id = st.session_state.active_user_id
    project_id = st.session_state.active_project_id
    repository = get_repository()
    try:
        job = repository.create_job(user_id, project_id, domain)
    except ProjectJobRunningError:
        st.error("A workflow job is already running for this Project. Wait for it to finish before continuing.")
        return False

    job_id = str(job["job_id"])
    st.session_state.streamlit_job_id = job_id
    st.session_state.streamlit_job_operation = operation
    submit_job(repository, user_id, job_id, domain, work)
    return True


def _refresh_active_project_state() -> None:
    """Replace the in-memory UI snapshot with the latest durable SQLite state."""
    repository = get_repository()
    user_id = st.session_state.active_user_id
    project_id = st.session_state.active_project_id
    stored = repository.load(user_id, project_id)
    if stored is None:
        return
    thread_id, state = stored
    state.resource_chunks = repository.load_resource_chunks(user_id, project_id)
    st.session_state.thread_id = thread_id
    st.session_state.state = state


@st.fragment(run_every=1.0)
def render_streamlit_job_monitor() -> None:
    """Poll a durable local job without blocking the Streamlit interface thread."""
    user_id = st.session_state.get("active_user_id")
    project_id = st.session_state.get("active_project_id")
    if not user_id or not project_id:
        return
    repository = get_repository()
    job_id = st.session_state.get("streamlit_job_id")
    job = repository.get_job(user_id, job_id) if job_id else repository.active_job(user_id, project_id)
    if job is None or job.get("project_id") != project_id:
        return
    status = str(job.get("status", "queued"))
    if status in {"queued", "running"}:
        st.info(f"Working: {str(job.get('stage', 'running')).replace('_', ' ')}")
        st.progress(int(job.get("progress", 0)))
        return

    if job_id == str(job.get("job_id")):
        _refresh_active_project_state()
        st.session_state.pop("streamlit_job_id", None)
        operation = st.session_state.pop("streamlit_job_operation", "operation")
        if status == "completed":
            st.session_state.streamlit_job_notice = ("success", f"{operation.replace('_', ' ').title()} completed.")
        else:
            st.session_state.streamlit_job_notice = (
                "error",
                str(job.get("error") or "The operation could not be completed. Please retry."),
            )
        st.rerun()


def open_or_create_project(user_id: str) -> None:
    """Create a human-named Project with an internal, stable identifier."""
    project_name = str(st.session_state.get("new_project_name_input", "")).strip()
    if not project_name:
        st.session_state.project_error = "Enter a Project name."
        return
    project_id = f"project-{uuid4()}"
    get_repository().create_empty(user_id, project_id, project_name)
    st.session_state.project_selector = project_id
    st.session_state.active_project_id = None
    st.session_state.new_project_name_input = ""
    st.session_state.pop("project_error", None)


def sign_out() -> None:
    if bool(st.secrets.get("AUTH_REQUIRED", False)):
        st.logout()
        return
    st.session_state.pop("local_authenticated_user_id", None)


def delete_active_project(user_id: str, project_id: str) -> None:
    get_repository().delete_project(user_id, project_id)
    remaining_projects = get_repository().list_projects(user_id)
    if remaining_projects:
        st.session_state.project_selector = remaining_projects[0]["id"]
    else:
        st.session_state.pop("project_selector", None)
    st.session_state.active_project_id = None
    st.session_state.pop("confirm_project_delete", None)


def delete_account(user_id: str) -> None:
    """Delete local data only after the user confirms in the sidebar."""
    get_repository().delete_user(user_id)
    sign_out()


def remove_resource(resource_id: str) -> None:
    state = st.session_state.get("state")
    if state is None:
        return
    try:
        RemoveProjectResourceUseCase().execute(state, resource_id)
        save_state()
        st.session_state.pop("pending_resource_delete", None)
        st.session_state.resource_deleted = True
    except ValueError as exc:
        st.session_state.resource_error = str(exc)


def run_validation(tool, **arguments: object) -> None:
    try:
        st.session_state.state = tool.func(st.session_state.state, **arguments)
        st.session_state.state.execution = ExecutionContext()
        save_state()
        st.success("Validation enregistrée.")
    except ValueError as exc:
        st.error(str(exc))


def review_item(use_case, index: int, comments: str) -> None:
    try:
        st.session_state.state = use_case.execute(st.session_state.state, index, comments)
        save_state()
        st.success("Élément validé et commentaire enregistré.")
    except ValueError as exc:
        st.error(str(exc))


def run_blueprint_regeneration() -> None:
    """Persist reviewer feedback, then regenerate in a durable background job."""
    try:
        presentation = st.session_state.state.presentation
        if presentation is not None and presentation.blueprint is not None:
            for index, outline in enumerate(presentation.blueprint.slides):
                comments = str(st.session_state.get(f"blueprint_comment_{index}", "")).strip()
                if comments:
                    outline.reviewer_comments = comments
                    outline.is_validated = False
        save_state(
            "BLUEPRINT_REGENERATION_REQUESTED",
            "user",
            {
                "commented_item_indexes": [
                    index
                    for index, outline in enumerate(presentation.blueprint.slides)
                    if outline.reviewer_comments
                ] if presentation and presentation.blueprint else []
            },
        )
        _queue_presentation_regeneration("blueprint")
    except ValueError as exc:
        st.error(str(exc))


def run_slide_regeneration(index: int, comments: str) -> None:
    """Persist the current slide comment, then regenerate it in a background job."""
    try:
        presentation = st.session_state.state.presentation
        if presentation is not None and 0 <= index < len(presentation.slides):
            normalized = comments.strip()
            if normalized:
                presentation.slides[index].reviewer_comments = normalized
                presentation.slides[index].is_validated = False
        save_state(
            "SLIDE_REGENERATION_REQUESTED",
            "user",
            {"slide_index": index, "has_comments": bool(comments.strip())},
        )
        _queue_presentation_regeneration("slide", slide_index=index)
    except ValueError as exc:
        st.error(str(exc))


def create_presentation_from_setup(
    topic: str,
    audience: AudienceType,
    presentation_type: PresentationType,
    language: Language,
    duration_minutes: int,
    objective: str,
    presenter_name: str = "",
    presenter_title: str = "",
    organization: str = "",
    event_name: str = "",
    venue: str = "",
    presentation_date: str = "",
) -> None:
    """Create a draft through explicit human input, never through chat intent."""
    try:
        state = st.session_state.state
        state = CollectPresentationContextUseCase().execute(
            state,
            topic=topic,
            audience=audience,
            presentation_type=presentation_type,
            language=language,
            duration_minutes=duration_minutes,
            objective=objective,
            presenter_name=presenter_name,
            presenter_title=presenter_title,
            organization=organization,
            event_name=event_name,
            venue=venue,
            presentation_date=presentation_date,
        )
        state = ValidatePresentationContextUseCase().execute(state)
        st.session_state.state = CreatePresentationWorkflowUseCase().execute(state)
        save_state()
        st.success("Presentation created. Select and validate its PDF evidence in Resources.")
    except ValueError as exc:
        st.error(str(exc))


def run_explicit_generation(action: str) -> None:
    """Queue a human-clicked generation command; chat never advances workflow state."""
    _queue_presentation_generation(action)


def _queue_presentation_generation(action: str) -> None:
    """Use the durable Project job lock for blueprint and slide generation."""
    if action not in {"blueprint", "slides"}:
        st.error("Unknown presentation generation action.")
        return
    user_id = st.session_state.active_user_id
    project_id = st.session_state.active_project_id
    repository = get_repository()

    def work(progress) -> dict[str, object]:
        thread_id, current_state = _load_current_project_for_job(repository, user_id, project_id)
        operation = f"generate_{action}"
        try:
            progress(25, f"validating_{action}_request")
            progress(55, f"generating_{action}")
            if action == "blueprint":
                current_state = BuildBlueprintWorkflowUseCase().execute(current_state)
                event_type = "BLUEPRINT_GENERATED_FROM_EXPLICIT_COMMAND"
            else:
                current_state = GenerateSlidesWorkflowUseCase().execute(current_state)
                event_type = "SLIDES_GENERATED_FROM_EXPLICIT_COMMAND"
            current_state.execution = ExecutionContext(last_tool=operation)
            progress(85, "persisting_project")
            repository.save_with_event(
                user_id,
                project_id,
                thread_id,
                current_state,
                event_type,
                "llm",
                {"generation_command": action, "interface": "streamlit"},
            )
            return {"project_id": project_id}
        except Exception as exc:
            raise _persist_streamlit_job_failure(
                repository,
                user_id,
                project_id,
                thread_id,
                current_state,
                operation,
                exc,
            ) from exc

    _queue_streamlit_job(f"presentation_{action}", f"generate_{action}", work)


def _queue_presentation_regeneration(action: str, slide_index: int | None = None) -> None:
    """Regenerate exactly one reviewed artefact behind the Project job lock."""
    if action not in {"blueprint", "slide"}:
        st.error("Unknown presentation regeneration action.")
        return
    user_id = st.session_state.active_user_id
    project_id = st.session_state.active_project_id
    repository = get_repository()

    def work(progress) -> dict[str, object]:
        thread_id, current_state = _load_current_project_for_job(repository, user_id, project_id)
        operation = f"regenerate_{action}"
        try:
            progress(25, f"validating_{action}_regeneration")
            progress(55, f"regenerating_{action}")
            if action == "blueprint":
                current_state = RegenerateBlueprintUseCase().execute(current_state)
                event_type = "BLUEPRINT_REGENERATED_FROM_EXPLICIT_COMMAND"
            else:
                if slide_index is None:
                    raise ValueError("A slide number is required for slide regeneration.")
                current_state = RegenerateSlideUseCase().execute(current_state, slide_index)
                event_type = "SLIDE_REGENERATED_FROM_EXPLICIT_COMMAND"
            current_state.execution = ExecutionContext(last_tool=operation)
            progress(85, "persisting_project")
            repository.save_with_event(
                user_id,
                project_id,
                thread_id,
                current_state,
                event_type,
                "llm",
                {
                    "generation_command": operation,
                    "interface": "streamlit",
                    **({"slide_index": slide_index} if slide_index is not None else {}),
                },
            )
            return {"project_id": project_id}
        except Exception as exc:
            raise _persist_streamlit_job_failure(
                repository,
                user_id,
                project_id,
                thread_id,
                current_state,
                operation,
                exc,
            ) from exc

    _queue_streamlit_job(
        f"presentation_regenerate_{action}",
        f"regenerate_{action}",
        work,
    )


def save_blueprint_edit(index: int, title: str, objective: str, key_message: str, origin: str) -> None:
    try:
        st.session_state.state = EditBlueprintItemUseCase().execute(
            st.session_state.state,
            index,
            title=title,
            objective=objective,
            key_message=key_message,
            content_origin=origin,
        )
        save_state()
        st.success("Blueprint item saved as user content. Re-approve the agenda and blueprint before generating slides.")
    except ValueError as exc:
        st.error(str(exc))


def author_blocked_slide(blueprint_index: int) -> None:
    """Create a clearly user-authored draft for one evidence-blocked outline."""
    if _project_job_is_running():
        return
    try:
        st.session_state.state = AuthorSlideFromBlueprintUseCase().execute(
            st.session_state.state,
            blueprint_index,
        )
        save_state(
            "BLOCKED_SLIDE_AUTHORED_BY_USER",
            "user",
            {"blueprint_item_index": blueprint_index, "interface": "streamlit"},
        )
        st.success("A user-authored slide draft was created. Edit and approve it when ready.")
    except ValueError as exc:
        st.error(str(exc))


def save_slide_edit(
    index: int,
    title: str,
    objective: str,
    key_messages: str,
    content: str,
    speaker_notes: str,
    origin: str,
) -> None:
    try:
        st.session_state.state = EditSlideUseCase().execute(
            st.session_state.state,
            index,
            title=title,
            objective=objective,
            key_messages=key_messages.splitlines(),
            content=content,
            speaker_notes=speaker_notes,
            content_origin=origin,
        )
        save_state()
        st.success("Slide saved as user content. It must be approved again before final export.")
    except ValueError as exc:
        st.error(str(exc))


def analyze_uploaded_resources() -> None:
    """Generate a source-only overview asynchronously without freezing Streamlit."""
    user_id = st.session_state.active_user_id
    project_id = st.session_state.active_project_id
    repository = get_repository()

    def work(progress) -> dict[str, object]:
        thread_id, current_state = _load_current_project_for_job(repository, user_id, project_id)
        operation = "resource_overview"
        try:
            progress(30, "retrieving_pdf_passages")
            analysis = SummarizeResourcesUseCase().execute(
                current_state.resource_library,
                language=current_state.user_profile.preferred_language,
                chunks=current_state.resource_chunks,
                evidence_context_mode=current_state.evidence_context_mode,
                patient_case_mode=current_state.patient_case_mode,
            )
            progress(65, "generating_overview")
            current_state.resource_analysis = analysis
            current_state.execution = ExecutionContext(last_tool=operation)
            progress(85, "persisting_project")
            repository.save_with_event(
                user_id,
                project_id,
                thread_id,
                current_state,
                "RESOURCE_ANALYSIS_GENERATED",
                "llm",
                {"resource_ids": analysis.resource_ids, "interface": "streamlit"},
            )
            return {"project_id": project_id}
        except Exception as exc:
            raise _persist_streamlit_job_failure(
                repository,
                user_id,
                project_id,
                thread_id,
                current_state,
                operation,
                exc,
                "RESOURCE_ANALYSIS_FAILED",
            ) from exc

    _queue_streamlit_job("resources", "resource_overview", work)


def discuss_uploaded_resources(question: str) -> None:
    """Persist a resource question first, then get its source-only answer in a job."""
    if _project_job_is_running():
        return
    state = st.session_state.state
    try:
        add_resource_turn(state, "user", question)
        save_state(
            "RESOURCE_DISCUSSION_MESSAGE_RECEIVED",
            "user",
            {"question_length": len(question)},
        )
    except ValueError as exc:
        st.session_state.resource_error = str(exc)
        return

    user_id = st.session_state.active_user_id
    project_id = st.session_state.active_project_id
    repository = get_repository()

    def work(progress) -> dict[str, object]:
        thread_id, current_state = _load_current_project_for_job(repository, user_id, project_id)
        operation = "resource_discussion"
        try:
            progress(30, "retrieving_pdf_passages")
            answer = DiscussResourcesUseCase().execute(
                current_state.resource_library,
                question,
                language=current_state.user_profile.preferred_language,
                chunks=current_state.resource_chunks,
                evidence_context_mode=current_state.evidence_context_mode,
                patient_case_mode=current_state.patient_case_mode,
            )
            progress(65, "generating_discussion")
            add_resource_turn(current_state, "assistant", answer)
            current_state.execution = ExecutionContext(last_tool=operation)
            progress(85, "persisting_project")
            repository.save_with_event(
                user_id,
                project_id,
                thread_id,
                current_state,
                "RESOURCE_DISCUSSION_COMPLETED",
                "llm",
                {"question_length": len(question), "interface": "streamlit"},
            )
            return {"project_id": project_id}
        except Exception as exc:
            raise _persist_streamlit_job_failure(
                repository,
                user_id,
                project_id,
                thread_id,
                current_state,
                operation,
                exc,
                "RESOURCE_DISCUSSION_FAILED",
            ) from exc

    _queue_streamlit_job("resources", "resource_discussion", work)


def queue_presentation_chat(message: str) -> None:
    """Persist a presentation-chat turn before asynchronously calling the model."""
    if _project_job_is_running():
        return
    state = st.session_state.state
    state.messages.append(HumanMessage(content=message))
    add_turn(state, "user", message)
    state.user_profile = get_repository().get_user_profile(st.session_state.active_user_id)
    if state.presentation is not None:
        state.presentation.owner_profile = state.user_profile
    try:
        save_state(
            "USER_MESSAGE_RECEIVED",
            "user",
            {"message_length": len(message)},
        )
    except ValueError as exc:
        st.error(str(exc))
        return

    user_id = st.session_state.active_user_id
    project_id = st.session_state.active_project_id
    repository = get_repository()

    def work(progress) -> dict[str, object]:
        thread_id, current_state = _load_current_project_for_job(repository, user_id, project_id)
        operation = "presentation_chat"
        try:
            progress(25, "preparing_conversation")
            progress(55, "calling_model")
            result = get_agent().invoke(current_state, thread_id)
            completed_state = GraphState(**result)
            ensure_history(completed_state)
            assistant_text = next(
                (
                    transcript_message_text(model_message)
                    for model_message in reversed(completed_state.messages)
                    if getattr(model_message, "type", "") == "ai"
                    and transcript_message_text(model_message)
                ),
                "",
            )
            if assistant_text and (
                not completed_state.conversation_history
                or completed_state.conversation_history[-1].role != "assistant"
                or completed_state.conversation_history[-1].text != assistant_text
            ):
                add_turn(completed_state, "assistant", assistant_text)
            progress(85, "persisting_project")
            repository.save_with_event(
                user_id,
                project_id,
                thread_id,
                completed_state,
                "AGENT_TURN_COMPLETED",
                "llm",
                {"message_length": len(message), "interface": "streamlit"},
            )
            return {"project_id": project_id, "message": assistant_text}
        except Exception as exc:
            raise _persist_streamlit_job_failure(
                repository,
                user_id,
                project_id,
                thread_id,
                current_state,
                operation,
                exc,
                "AGENT_TURN_FAILED",
            ) from exc

    _queue_streamlit_job("conversation", "presentation_chat", work)


def message_text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
    return str(content)


def render_model_message(text: str, resources) -> None:
    """Render readable source titles while retaining technical IDs on demand."""
    st.markdown(format_citations_for_display(text, resources))
    details = citation_display_details(text, resources)
    if details:
        with st.expander("Technical citation details", expanded=False):
            for detail in details:
                location = f" · p. {detail.pages}" if detail.pages else ""
                st.caption(f"{detail.title}{location}")
                st.code(f"resource_id: {detail.resource_id}", language=None)


st.title("🩺 Healthcare Presentation Assistant")
st.caption("Discuss ideas, then create a scientific presentation from validated PDF resources.")

with st.sidebar:
    user_id = authenticated_user_id()
    if st.session_state.get("active_user_id") != user_id:
        st.session_state.pop("project_selector", None)

    profile = get_repository().get_user_profile(user_id)
    st.markdown(
        """<style>
        .profile-summary {display:flex; align-items:center; gap:.55rem; margin:.2rem 0 .45rem;}
        .profile-emblem {width:2.35rem;height:2.35rem;display:grid;place-items:center;border-radius:.7rem;background:#e7f4f1;color:#087f73;}
        .profile-emblem svg {width:1.65rem;height:1.65rem;fill:none;stroke:currentColor;stroke-width:2.15;stroke-linecap:round;stroke-linejoin:round;}
        .profile-summary strong {font-size:.96rem;}
        .resource-row {display:flex;align-items:center;justify-content:space-between;gap:.45rem;padding:.35rem 0;border-bottom:1px solid #edf0f2;}
        .resource-row small {display:block;color:#64748b;overflow-wrap:anywhere;}
        </style>""",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="profile-summary"><span class="profile-emblem">{role_emblem(profile.professional_role)}</span><strong>{role_label(profile.professional_role)}</strong></div>',
        unsafe_allow_html=True,
    )
    with st.expander(f"User · {user_id}", expanded=False):
        role = st.selectbox(
            "Professional profile",
            options=ROLE_OPTIONS,
            index=ROLE_OPTIONS.index(profile.professional_role),
            format_func=role_label,
        )
        language = st.selectbox(
            "Language",
            options=["en", "fr", "ar"],
            index=["en", "fr", "ar"].index(profile.preferred_language),
        )
        selected_profile = UserProfile(professional_role=role, preferred_language=language)
        if selected_profile != profile:
            get_repository().update_user_profile(user_id, selected_profile)
            profile = selected_profile
            st.rerun()
        if st.button("Sign out", use_container_width=True):
            sign_out()
            st.rerun()
        if not bool(st.secrets.get("AUTH_REQUIRED", False)):
            if st.button("Delete my account", type="secondary", use_container_width=True):
                st.session_state.confirm_account_delete = True
            if st.session_state.get("confirm_account_delete"):
                st.warning("This permanently deletes your account, Projects and conversation history.")
                confirm, cancel = st.columns(2)
                if confirm.button("Delete permanently", type="primary", use_container_width=True):
                    delete_account(user_id)
                    st.rerun()
                if cancel.button("Cancel", use_container_width=True):
                    st.session_state.pop("confirm_account_delete", None)
                    st.rerun()

    projects = get_repository().list_projects(user_id)
    if not projects:
        first_project_id = f"project-{uuid4()}"
        get_repository().create_empty(user_id, first_project_id, "My first Project")
        projects = get_repository().list_projects(user_id)
    project_ids = [project["id"] for project in projects]
    project_names = {project["id"]: project["name"] for project in projects}
    default_project = st.session_state.get("project_selector", project_ids[0])
    if default_project not in project_names:
        default_project = project_ids[0]
    with st.expander(f"Project · {project_names[default_project]}", expanded=True):
        project_id = st.selectbox(
            "Project",
            options=project_ids,
            index=project_ids.index(default_project),
            key="project_selector",
            format_func=lambda item: project_names[item],
            help="Each Project retains its own conversation, resources and presentation.",
        )
        st.text_input(
            "Name of the new Project",
            placeholder="e.g. Depression for general practice",
            max_chars=128,
            key="new_project_name_input",
        )
        st.button("Create Project", on_click=open_or_create_project, args=(user_id,), use_container_width=True)
        if project_error := st.session_state.pop("project_error", None):
            st.error(project_error)
        if st.button("Delete this Project", type="secondary", use_container_width=True):
            st.session_state.confirm_project_delete = project_id
        if st.session_state.get("confirm_project_delete") == project_id:
            st.warning("This permanently deletes this Project and its conversation history.")
            confirm, cancel = st.columns(2)
            confirm.button(
                "Delete Project",
                type="primary",
                use_container_width=True,
                on_click=delete_active_project,
                args=(user_id, project_id),
            )
            if cancel.button("Cancel", use_container_width=True):
                st.session_state.pop("confirm_project_delete", None)
                st.rerun()

    state = load_project_state(user_id, project_id)
    if ensure_history(state):
        save_state()
    if state.user_profile != profile:
        state.user_profile = profile
        if state.presentation is not None:
            state.presentation.owner_profile = profile
        save_state("USER_PROFILE_APPLIED_TO_PROJECT", "user", {"interface": "streamlit"})
    st.caption(f"Project · Session {st.session_state.thread_id[:8]}")

job_notice = st.session_state.pop("streamlit_job_notice", None)
if job_notice:
    level, message = job_notice
    getattr(st, level)(message)
render_streamlit_job_monitor()
active_project_job = get_repository().active_job(user_id, project_id)
if active_project_job:
    st.info(
        "A Project operation is running. You can read the current workspace; "
        "state-changing actions remain disabled until it finishes."
    )

workspace_key = f"active_workspace_{user_id}_{project_id}"
workspace = st.segmented_control(
    "Workspace",
    options=("Presentation Studio", "Resources", "Resource Analysis"),
    default="Presentation Studio",
    key=workspace_key,
)
resource_validation_required = WorkflowPolicy.requires_resource_validation(state.presentation)

if workspace == "Resources":
    st.header("Resources")
    st.caption("Upload, select and validate the PDF evidence used for presentation production.")
    with st.expander("Evidence and Patient Case Mode", expanded=False):
        st.caption(
            "Evidence mode changes passage selection only. Validation, provenance and human approval remain required."
        )
        selected_evidence_mode = st.selectbox(
            "Evidence context mode",
            options=list(EvidenceContextMode),
            index=list(EvidenceContextMode).index(state.evidence_context_mode),
            format_func=lambda mode: {
                EvidenceContextMode.BM25: "BM25 retrieval — default",
                EvidenceContextMode.DIRECT_BOUNDED: "Direct bounded PDF context — experimental",
            }[mode],
        )
        patient_case_mode = st.checkbox(
            "Enable Patient Case Mode (de-identified information only)",
            value=state.patient_case_mode,
        )
        patient_case_acknowledged = st.checkbox(
            "I confirm that no patient-identifying information will be entered or uploaded.",
            value=state.patient_case_acknowledged,
            disabled=not patient_case_mode,
        )
        if patient_case_mode:
            st.warning(
                "HPA detects obvious identifiers before LLM use, but cannot guarantee de-identification. "
                "Remove patient names, full dates, identifiers, contact details and addresses."
            )
        if st.button("Save evidence settings", use_container_width=True, disabled=bool(active_project_job)):
            try:
                UpdateProjectEvidenceSettingsUseCase().execute(
                    state,
                    evidence_context_mode=selected_evidence_mode,
                    patient_case_mode=patient_case_mode,
                    patient_case_acknowledged=patient_case_acknowledged,
                )
                save_state()
                st.success("Evidence settings saved.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    uploaded_pdf = st.file_uploader("Upload a PDF", type=["pdf"])
    if st.button("Add resource", disabled=uploaded_pdf is None or bool(active_project_job), use_container_width=True):
        if uploaded_pdf.size > 20 * 1024 * 1024:
            st.error("PDF files are limited to 20 MB.")
        else:
            try:
                resource = ExtractPdfResourceUseCase().execute(
                    uploaded_pdf.name,
                    uploaded_pdf.getvalue(),
                    patient_case_mode=state.patient_case_mode,
                )
                AddProjectResourceUseCase().execute(state, resource)
                save_state()
                st.success(f"{resource.filename} was added to this Project library.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    if not state.resource_library:
        st.info("Upload a PDF to build this Project's source library.")
    else:
        st.subheader("Project resource library")
        attached_ids = {resource.id for resource in state.presentation.resources} if state.presentation else set()
        for resource in state.resource_library:
            label, action, remove = st.columns([5, 2, 1])
            label.markdown(
                f"<div class=\"resource-row\"><div><strong>{resource.filename}</strong>"
                f"<small>{'Selected for production' if resource.id in attached_ids else 'Library only'}</small></div></div>",
                unsafe_allow_html=True,
            )
            if state.presentation:
                if resource.id in attached_ids:
                    if action.button("Detach", key=f"detach_resource_{resource.id}", use_container_width=True, disabled=bool(active_project_job)):
                        try:
                            DetachResourceFromPresentationUseCase().execute(state, resource.id)
                            save_state()
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                elif action.button("Use in presentation", key=f"attach_resource_{resource.id}", use_container_width=True, disabled=bool(active_project_job)):
                    try:
                        AttachResourceToPresentationUseCase().execute(state, resource.id)
                        save_state()
                        st.success("Resource selected for production evidence.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
            if remove.button("×", key=f"remove_resource_{resource.id}", help="Remove resource", disabled=bool(active_project_job)):
                st.session_state.pending_resource_delete = resource.id
        pending_resource = st.session_state.get("pending_resource_delete")
        if pending_resource:
            st.warning("Removing a resource resets generated content and approvals based on that evidence.")
            confirm, cancel = st.columns(2)
            if confirm.button("Remove resource", type="primary", use_container_width=True, disabled=bool(active_project_job)):
                remove_resource(pending_resource)
                st.rerun()
            if cancel.button("Cancel", use_container_width=True):
                st.session_state.pop("pending_resource_delete", None)
                st.rerun()
    if resource_validation_required:
        st.info("The selected resources need your approval before the blueprint can be generated.")
        st.button(
            "Validate resources and continue",
            type="primary",
            on_click=run_validation,
            args=(validate_resources,),
            key="resource_workspace_validate_resources",
            disabled=bool(active_project_job),
        )
    elif state.presentation and state.presentation.state.resources_validated:
        st.success("Resources are validated for production.")
        if st.button("Continue to Presentation Studio", type="primary", disabled=bool(active_project_job)):
            st.session_state[workspace_key] = "Presentation Studio"
            st.rerun()
        if state.presentation.state.workflow_status == WorkflowStatus.BLUEPRINT_GENERATION:
            st.button(
                "Generate blueprint",
                on_click=run_explicit_generation,
                args=("blueprint",),
                disabled=bool(active_project_job),
                use_container_width=True,
            )
    if st.session_state.pop("resource_deleted", False):
        st.success("Resource removed. Dependent generated content and approvals were reset.")
    if resource_error := st.session_state.pop("resource_error", None):
        st.error(resource_error)
    st.stop()

if workspace == "Resource Analysis":
    st.header("Resource Analysis")
    st.caption("Explore uploaded PDFs without selecting, validating or generating presentation content.")
    if not state.resource_library:
        st.info("Upload a PDF first in Resources.")
        st.stop()

    analyze_column, status_column = st.columns([1, 2])
    analyze_column.button(
        "Analyze uploaded resources",
        on_click=analyze_uploaded_resources,
        use_container_width=True,
        disabled=bool(active_project_job),
    )
    status_column.caption(f"{len(state.resource_library)} PDF resource(s) in this Project library")
    st.divider()

    st.subheader("Resource overview")
    st.caption("AI-generated discussion starter based only on the uploaded PDF resources.")
    if state.resource_analysis:
        render_model_message(state.resource_analysis.summary, state.resource_library)
    else:
        st.info("Select Analyze uploaded resources to generate a source-only overview.")

    st.divider()
    st.subheader("Resource chat")
    st.caption("This discussion is separate from the Presentation assistant chat.")
    for turn in state.resource_conversation_history:
        with st.chat_message(turn.role):
            if turn.role == "assistant":
                render_model_message(turn.text, state.resource_library)
            else:
                st.write(turn.text)
    resource_question = st.chat_input(
        "Ask a question answered only from the uploaded PDFs",
        key=f"resource_discussion_question_{project_id}",
        disabled=bool(active_project_job),
    )
    if resource_question:
        discuss_uploaded_resources(resource_question)
        if error := st.session_state.pop("resource_error", None):
            st.error(error)
        st.rerun()
    st.stop()

st.header("Presentation Studio")
st.caption("Human-controlled workflow. Chat can assist with discussion, but it cannot create or generate presentation content.")

if state.presentation:
    with st.expander("Title-slide details", expanded=False):
        st.caption("Optional human-supplied details. Empty fields are not shown on the PowerPoint title slide.")
        context = state.presentation.context
        presenter_name = st.text_input("Presenter name", value=context.presenter_name or "")
        presenter_title = st.text_input("Professional title", value=context.presenter_title or "")
        organization = st.text_input("Organization", value=context.organization or "")
        event_name = st.text_input("Event name", value=context.event_name or "")
        venue = st.text_input("Venue", value=context.venue or "")
        presentation_date = st.text_input("Presentation date", value=context.presentation_date or "")
        if st.button("Save title-slide details", use_container_width=True):
            try:
                UpdatePresentationDetailsUseCase().execute(
                    state,
                    presenter_name=presenter_name,
                    presenter_title=presenter_title,
                    organization=organization,
                    event_name=event_name,
                    venue=venue,
                    presentation_date=presentation_date,
                )
                save_state()
                st.success("Title-slide details saved.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    selected_theme = st.selectbox(
        "PowerPoint template",
        options=list(PresentationTheme),
        index=list(PresentationTheme).index(state.presentation.theme),
        format_func=lambda theme: {
            PresentationTheme.CLINICAL: "Clinical clarity",
            PresentationTheme.ACADEMIC: "Academic prestige",
            PresentationTheme.EXECUTIVE: "Executive impact",
            PresentationTheme.MIDNIGHT: "Midnight focus",
        }[theme],
    )
    if selected_theme != state.presentation.theme:
        state.presentation.theme = selected_theme
        save_state()
    if state.presentation.slides:
        try:
            render_presentation_preview(
                state.presentation,
                resolve_presentation_resources(state),
                project_id,
            )
        except ValueError as exc:
            st.warning(f"Presentation preview is unavailable: {exc}")
    if state.presentation.state.slides_validated and not state.presentation.state.presentation_validated:
        st.button(
            "Approve final presentation",
            on_click=run_validation,
            args=(validate_final_presentation,),
            kwargs={"approved": True},
            use_container_width=True,
        )
    if st.button("Prepare PowerPoint", disabled=not state.presentation.state.presentation_validated):
        try:
            with TemporaryDirectory() as directory:
                path = ExportPowerPointUseCase().execute(
                    state.presentation,
                    Path(directory),
                    resources=resolve_presentation_resources(state),
                )
                st.session_state.pptx_data = path.read_bytes()
                st.session_state.pptx_name = f"{state.presentation.title}.pptx"
        except ValueError as exc:
            st.error(str(exc))
    if "pptx_data" in st.session_state:
        st.download_button(
            "Download PowerPoint",
            st.session_state.pptx_data,
            st.session_state.pptx_name,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )

if state.presentation is None:
    st.caption("Create the presentation through explicit human-controlled fields.")
    collected_context = state.conversation_context
    default_audience = (
        collected_context.audience
        if isinstance(collected_context.audience, AudienceType)
        else AudienceType.GENERAL_PRACTITIONER
    )
    default_type = (
        collected_context.presentation_type
        if isinstance(collected_context.presentation_type, PresentationType)
        else PresentationType.LECTURE
    )
    default_language = (
        collected_context.language
        if isinstance(collected_context.language, Language)
        else Language.ENGLISH
    )
    with st.form("presentation_setup_form"):
        setup_topic = st.text_input("Presentation topic", value=collected_context.topic or "", max_chars=500)
        first, second, third = st.columns(3)
        setup_audience = first.selectbox(
            "Target audience",
            options=list(AudienceType),
            index=list(AudienceType).index(default_audience),
        )
        setup_type = second.selectbox(
            "Presentation type",
            options=list(PresentationType),
            index=list(PresentationType).index(default_type),
        )
        setup_language = third.selectbox(
            "Presentation language",
            options=list(Language),
            index=list(Language).index(default_language),
        )
        setup_duration = st.number_input(
            "Duration (minutes)",
            min_value=1,
            max_value=480,
            value=collected_context.duration_minutes or 10,
        )
        setup_objective = st.text_area(
            "Presentation objective",
            value=collected_context.objective or "",
            max_chars=4000,
        )
        with st.expander("Title-slide details (optional)", expanded=False):
            st.caption("These details are displayed only if you provide them; the assistant never infers them.")
            setup_presenter_name = st.text_input("Presenter name", value=collected_context.presenter_name or "")
            setup_presenter_title = st.text_input("Professional title", value=collected_context.presenter_title or "")
            setup_organization = st.text_input("Organization", value=collected_context.organization or "")
            setup_event_name = st.text_input("Event name", value=collected_context.event_name or "")
            setup_venue = st.text_input("Venue", value=collected_context.venue or "")
            setup_presentation_date = st.text_input("Presentation date", value=collected_context.presentation_date or "")
        setup_submit = st.form_submit_button("Create presentation", type="primary")
    if setup_submit:
        if not setup_topic.strip() or not setup_objective.strip():
            st.error("Presentation topic and objective are required.")
        else:
            create_presentation_from_setup(
                setup_topic.strip(),
                setup_audience,
                setup_type,
                setup_language,
                int(setup_duration),
                setup_objective.strip(),
                setup_presenter_name.strip(),
                setup_presenter_title.strip(),
                setup_organization.strip(),
                setup_event_name.strip(),
                setup_venue.strip(),
                setup_presentation_date.strip(),
            )
            st.rerun()
    st.info("After creation, select PDFs in Resources and validate them before blueprint generation.")

if resource_validation_required:
    st.divider()
    st.subheader("Human validation required")
    st.info("The assistant needs your validation before it can generate the blueprint.")
    st.button(
        "Validate resources and continue",
        type="primary",
        on_click=run_validation,
        args=(validate_resources,),
        key="contextual_validate_resources",
    )

if (
    state.presentation
    and state.presentation.state.workflow_status == WorkflowStatus.AWAITING_SCOPE_CLARIFICATION
):
    st.divider()
    st.subheader("Professional scope declaration")
    st.caption(
        "This workflow check is completed by you, not by the assistant. State your role and purpose, "
        "then confirm that the presentation is within your professional scope."
    )
    existing_declaration = state.presentation.professional_scope_declaration
    with st.form("professional_scope_declaration_form"):
        declared_role = st.text_input(
            "Your current professional role",
            value=existing_declaration.declared_role if existing_declaration else "",
            max_chars=200,
        )
        delivery_purpose = st.text_area(
            "Why this presentation is within your professional scope",
            value=existing_declaration.delivery_purpose if existing_declaration else "",
            max_chars=1_000,
        )
        confirmed_within_scope = st.checkbox(
            "I confirm that this presentation is within my professional scope.",
            value=bool(existing_declaration and existing_declaration.confirmed_within_scope),
        )
        save_scope = st.form_submit_button("Confirm professional scope", type="primary")
    if save_scope:
        try:
            st.session_state.state = RecordProfessionalScopeUseCase().execute(
                state,
                declared_role=declared_role,
                delivery_purpose=delivery_purpose,
                confirmed_within_scope=confirmed_within_scope,
            )
            st.session_state.state.execution = ExecutionContext(
                last_tool="record_professional_scope_declaration"
            )
            save_state()
            st.success("Professional scope declaration saved.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

if (
    state.presentation
    and state.presentation.state.workflow_status == WorkflowStatus.AWAITING_SLIDE_RESOLUTION
):
    st.subheader("Slides requiring a decision")
    blockers = state.presentation.state.slide_generation_blockers
    for blocker in blockers:
        st.warning(f"Slide {blocker.slide_number}: {blocker.message}")
        diagnostic = blocker.diagnostic
        if diagnostic:
            with st.expander(f"Evidence diagnostic — slide {blocker.slide_number}", expanded=False):
                st.json(diagnostic)
        blueprint_index = next(
            (
                index
                for index, outline in enumerate(state.presentation.blueprint.slides)
                if outline.slide_number == blocker.slide_number
            ),
            None,
        ) if state.presentation.blueprint else None
        if blueprint_index is not None:
            st.button(
                f"Write slide {blocker.slide_number} myself",
                on_click=author_blocked_slide,
                args=(blueprint_index,),
                key=f"author_blocked_slide_{blocker.slide_number}",
                disabled=bool(active_project_job),
            )
    if any(blocker.code == "INVALID_AI_PROVENANCE" for blocker in blockers):
        st.button(
            "Retry remaining slide generation",
            type="primary",
            on_click=run_explicit_generation,
            args=("slides",),
            key="retry_remaining_slides_command",
            disabled=bool(active_project_job),
        )

if state.presentation and state.presentation.state.workflow_status == WorkflowStatus.BLUEPRINT_GENERATION:
    st.subheader("Blueprint generation")
    st.caption("This action is controlled by the workflow and uses only selected, human-validated PDFs.")
    st.button(
        "Generate blueprint",
        type="primary",
        on_click=run_explicit_generation,
        args=("blueprint",),
        key="generate_blueprint_command",
        disabled=bool(active_project_job),
    )

if state.presentation and state.presentation.state.workflow_status == WorkflowStatus.SLIDE_GENERATION:
    st.subheader("Slide generation")
    st.caption("This action is controlled by the workflow and validates available evidence before model generation.")
    st.button(
        "Generate slides",
        type="primary",
        on_click=run_explicit_generation,
        args=("slides",),
        key="generate_slides_command",
        disabled=bool(active_project_job),
    )

if state.presentation and state.presentation.blueprint:
    st.divider()
    if state.presentation.agenda:
        st.subheader("Agenda — slide 2")
        st.caption("Proposed from the AI blueprint. Save your changes, then approve the agenda before approving the blueprint.")
        agenda_items = st.text_area(
            "Agenda items (one per line)",
            value="\n".join(state.presentation.agenda.items),
            key="agenda_items",
        )
        agenda_comments = st.text_area(
            "Agenda review comment",
            value=state.presentation.agenda.reviewer_comments or "",
            key="agenda_comments",
        )
        save_agenda, approve_agenda = st.columns(2)
        if save_agenda.button("Save agenda"):
            items = [item.strip() for item in agenda_items.splitlines() if item.strip()]
            if not items:
                st.error("Agenda must contain at least one item.")
            else:
                state.presentation.agenda.items = items
                state.presentation.agenda.reviewer_comments = agenda_comments.strip() or None
                state.presentation.agenda.is_validated = False
                state.presentation.blueprint.is_validated = False
                state.presentation.state.blueprint_validated = False
                state.presentation.state.slides_validated = False
                state.presentation.state.presentation_validated = False
                save_state()
                st.success("Agenda saved. Approve it when ready.")
        if approve_agenda.button("Approve agenda", disabled=state.presentation.agenda.is_validated):
            state.presentation.agenda.is_validated = True
            save_state()
            st.success("Agenda approved.")
    if st.toggle("Afficher et réviser le blueprint", key="show_blueprint"):
        outlines = state.presentation.blueprint.slides
        index = min(st.session_state.get("blueprint_index", 0), len(outlines) - 1)
        st.session_state.blueprint_index = index
        outline = outlines[index]
        previous, counter, next_item = st.columns([1, 2, 1])
        if previous.button("← Précédent", disabled=index == 0, key="blueprint_previous"):
            st.session_state.blueprint_index = index - 1
            st.rerun()
        counter.markdown(f"**Élément {index + 1} / {len(outlines)}**")
        if next_item.button("Suivant →", disabled=index == len(outlines) - 1, key="blueprint_next"):
            st.session_state.blueprint_index = index + 1
            st.rerun()
        st.subheader(outline.title)
        st.write(f"**Objectif :** {outline.objective}")
        st.write(f"**Message clé :** {outline.key_message}")
        st.caption(
            {
                "ai_generated": "AI-generated content",
                "user_edited": "User-edited content",
                "user_authored": "User-authored content",
            }[outline.content_origin]
        )
        with st.expander("Edit this blueprint item", expanded=False):
            edited_title = st.text_input("Title", value=outline.title, key=f"blueprint_edit_title_{index}_{outline.content_origin}")
            edited_objective = st.text_area("Objective", value=outline.objective, key=f"blueprint_edit_objective_{index}_{outline.content_origin}")
            edited_key_message = st.text_area("Key message", value=outline.key_message, key=f"blueprint_edit_message_{index}_{outline.content_origin}")
            origin = st.radio(
                "Content origin",
                options=["user_edited", "user_authored"],
                index=0 if outline.content_origin != "user_authored" else 1,
                format_func=lambda value: "Edited from AI content" if value == "user_edited" else "Written by user",
                key=f"blueprint_edit_origin_{index}_{outline.content_origin}",
            )
            if st.button("Save user edit", key=f"blueprint_edit_save_{index}"):
                save_blueprint_edit(index, edited_title, edited_objective, edited_key_message, origin)
                st.rerun()
        comments = st.text_area("Commentaire du relecteur", value=outline.reviewer_comments or "", key=f"blueprint_comment_{index}")
        approve, reject = st.columns(2)
        approve.button("Valider cet élément", disabled=outline.is_validated, on_click=review_item, args=(ReviewBlueprintItemUseCase(), index, comments), key=f"blueprint_validate_{index}")
        reject.button("Refuser / demander correction", on_click=review_item, args=(RejectBlueprintItemUseCase(), index, comments), key=f"blueprint_reject_{index}")
        st.button("Régénérer le blueprint avec les commentaires", on_click=run_blueprint_regeneration, key="blueprint_regenerate")
        if outline.is_validated:
            st.success("Élément validé.")

if state.presentation and state.presentation.slides:
    st.divider()
    if st.toggle("Afficher et réviser les slides", key="show_slides"):
        slides = state.presentation.slides
        index = min(st.session_state.get("slide_index", 0), len(slides) - 1)
        st.session_state.slide_index = index
        slide = slides[index]
        previous, counter, next_item = st.columns([1, 2, 1])
        if previous.button("← Précédente", disabled=index == 0, key="slide_previous"):
            st.session_state.slide_index = index - 1
            st.rerun()
        counter.markdown(f"**Slide {index + 1} / {len(slides)}**")
        if next_item.button("Suivante →", disabled=index == len(slides) - 1, key="slide_next"):
            st.session_state.slide_index = index + 1
            st.rerun()
        st.subheader(slide.title)
        st.write(slide.content)
        st.markdown("**Messages clés**")
        st.write(slide.key_messages)
        st.caption(
            {
                "ai_generated": "AI-generated content",
                "user_edited": "User-edited content",
                "user_authored": "User-authored content",
            }[slide.content_origin]
        )
        with st.expander("Edit this slide", expanded=False):
            edited_title = st.text_input("Title", value=slide.title, key=f"slide_edit_title_{index}_{slide.content_origin}")
            edited_objective = st.text_area("Objective", value=slide.objective or "", key=f"slide_edit_objective_{index}_{slide.content_origin}")
            edited_messages = st.text_area(
                "Key messages (one per line)",
                value="\n".join(slide.key_messages),
                key=f"slide_edit_messages_{index}_{slide.content_origin}",
            )
            edited_content = st.text_area("Slide content", value=slide.content, key=f"slide_edit_content_{index}_{slide.content_origin}")
            edited_notes = st.text_area("Speaker notes", value=slide.speaker_notes or "", key=f"slide_edit_notes_{index}_{slide.content_origin}")
            origin = st.radio(
                "Content origin",
                options=["user_edited", "user_authored"],
                index=0 if slide.content_origin != "user_authored" else 1,
                format_func=lambda value: "Edited from AI content" if value == "user_edited" else "Written by user",
                key=f"slide_edit_origin_{index}_{slide.content_origin}",
            )
            if st.button("Save user edit", key=f"slide_edit_save_{index}"):
                save_slide_edit(index, edited_title, edited_objective, edited_messages, edited_content, edited_notes, origin)
                st.rerun()
        if slide.reference_details and slide.content_origin == "ai_generated":
            st.markdown("**Preuves vérifiées**")
            for reference in slide.reference_details:
                st.caption(
                    f"{reference.get('title', 'Source')} · ID {reference.get('resource_id')} "
                    f"· page {reference.get('page')}"
                )
                st.info(f"« {reference.get('evidence_excerpt')} »")
        comments = st.text_area("Commentaire du relecteur", value=slide.reviewer_comments or "", key=f"slide_comment_{index}")
        approve, reject = st.columns(2)
        approve.button("Valider cette slide", disabled=slide.is_validated, on_click=review_item, args=(ReviewSlideUseCase(), index, comments), key=f"slide_validate_{index}")
        reject.button("Refuser / demander correction", on_click=review_item, args=(RejectSlideUseCase(), index, comments), key=f"slide_reject_{index}")
        st.button("Régénérer cette slide", on_click=run_slide_regeneration, args=(index, comments), key=f"slide_regenerate_{index}")
        if slide.is_validated:
            st.success("Slide validée.")

for turn in state.conversation_history:
    with st.chat_message(turn.role):
        if turn.role == "assistant":
            render_model_message(turn.text, state.resource_library)
        else:
            st.write(turn.text)

if prompt := st.chat_input("Discutez d’une idée ou demandez explicitement de créer/générer votre présentation..."):
    queue_presentation_chat(prompt)
    st.rerun()
