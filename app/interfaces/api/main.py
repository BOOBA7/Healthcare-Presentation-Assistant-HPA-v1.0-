from functools import lru_cache
import logging
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.ai.agents.healthcare_presentation_agent import HealthcarePresentationAgent
from app.ai.workflows.graph_state import GraphState
from app.application.use_cases.export_powerpoint import ExportPowerPointUseCase
from app.application.use_cases.extract_pdf_resource import ExtractPdfResourceUseCase
from app.application.use_cases.summarize_resources import SummarizeResourcesUseCase
from app.application.use_cases.discuss_resources import DiscussResourcesUseCase
from app.application.use_cases.update_presentation_details import UpdatePresentationDetailsUseCase
from app.application.use_cases.update_project_evidence_settings import UpdateProjectEvidenceSettingsUseCase
from app.application.use_cases.workflow_steps import (
    CollectPresentationContextUseCase,
    CreatePresentationWorkflowUseCase,
    ValidatePresentationContextUseCase,
)
from app.application.use_cases.manage_project_resources import (
    AddProjectResourceUseCase,
    AttachResourceToPresentationUseCase,
    DetachResourceFromPresentationUseCase,
    RemoveProjectResourceUseCase,
)
from app.application.services.workflow_policy import WorkflowPolicy
from app.application.services.workflow_view import WorkflowViewBuilder
from app.application.services.conversation_history import add_resource_turn, add_turn, ensure_history
from app.application.services.resource_library import ensure_resource_library, resolve_presentation_resources
from app.core.config import get_settings
from app.core.versioning import HARNESS_VERSION, RETRIEVAL_VERSION, WORKFLOW_VERSION
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.domain.enums.presentation_theme import PresentationTheme
from app.domain.enums.evidence_context_mode import EvidenceContextMode
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.exceptions.domain_error import DomainError
from app.domain.models.execution_context import ExecutionContext
from app.application.services.patient_case_privacy import PatientCasePrivacyGuard
from app.application.use_cases.workflow_steps import (
    RegenerateBlueprintUseCase,
    RegenerateSlideUseCase,
    EditBlueprintItemUseCase,
    EditSlideUseCase,
    RejectBlueprintItemUseCase,
    RejectSlideUseCase,
    ReviewBlueprintItemUseCase,
    ReviewSlideUseCase,
)
from app.ai.workflows.tools import (
    validate_blueprint,
    validate_final_presentation,
    validate_resources,
    validate_slides,
)

settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Healthcare Presentation Assistant API",
)
_exports_dir = Path("exports")
_web_dir = Path(__file__).resolve().parent.parent / "web"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    user_id: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=128)


class ProjectRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=128)
    project_name: str | None = Field(default=None, min_length=1, max_length=128)


class CredentialsRequest(BaseModel):
    user_id: str = Field(min_length=3, max_length=128, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=256)


class RegistrationRequest(CredentialsRequest):
    professional_role: str = "resident_physician"
    preferred_language: str = "en"


class UserProfileRequest(BaseModel):
    professional_role: str
    preferred_language: str


class ReviewRequest(BaseModel):
    comments: str = Field(default="", max_length=10_000)


class BlueprintItemEditRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    objective: str = Field(min_length=1, max_length=4_000)
    key_message: str = Field(min_length=1, max_length=4_000)
    content_origin: str = Field(pattern=r"^(user_edited|user_authored)$")


class SlideEditRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    objective: str = Field(default="", max_length=4_000)
    key_messages: list[str] = Field(default_factory=list, max_length=24)
    content: str = Field(default="", max_length=20_000)
    speaker_notes: str = Field(default="", max_length=20_000)
    content_origin: str = Field(pattern=r"^(user_edited|user_authored)$")


class AgendaRequest(BaseModel):
    items: list[str] = Field(min_length=1, max_length=12)
    comments: str = Field(default="", max_length=10_000)


class ThemeRequest(BaseModel):
    theme: PresentationTheme | None = None
    custom_template_id: str | None = Field(default=None, min_length=1, max_length=128)


class PresentationDetailsRequest(BaseModel):
    presenter_name: str = Field(default="", max_length=200)
    presenter_title: str = Field(default="", max_length=200)
    organization: str = Field(default="", max_length=300)
    event_name: str = Field(default="", max_length=300)
    venue: str = Field(default="", max_length=300)
    presentation_date: str = Field(default="", max_length=100)


class ProjectEvidenceSettingsRequest(BaseModel):
    evidence_context_mode: EvidenceContextMode = EvidenceContextMode.BM25
    patient_case_mode: bool = False
    patient_case_acknowledged: bool = False


class PresentationSetupRequest(BaseModel):
    """Human-entered fields required to create a production presentation."""

    topic: str = Field(min_length=1, max_length=500)
    audience: AudienceType
    presentation_type: PresentationType
    language: Language
    duration_minutes: int = Field(gt=0, le=480)
    objective: str = Field(min_length=1, max_length=4_000)
    # Title-slide details are optional and must remain explicitly human supplied.
    # They are never inferred by the LLM.
    presenter_name: str | None = Field(default=None, max_length=200)
    presenter_title: str | None = Field(default=None, max_length=200)
    organization: str | None = Field(default=None, max_length=300)
    event_name: str | None = Field(default=None, max_length=300)
    venue: str | None = Field(default=None, max_length=300)
    presentation_date: str | None = Field(default=None, max_length=100)


class ResourceDiscussionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=20_000)


def _message_text(content: object) -> str:
    """Normalize provider-specific message content before returning chat history."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ).strip()
    return str(content)


def _configured_model_identity() -> dict[str, str]:
    """Return configured provider metadata without exposing credentials."""
    provider = settings.llm_provider.lower()
    model = settings.openai_model if provider == "openai" else settings.gemini_model
    return {"provider": provider, "model": model}


def _provider_failure(exc: Exception) -> tuple[str, bool, int, str]:
    """Classify provider failures for safe audit records and HTTP responses."""
    message = str(exc)
    if "RESOURCE_EXHAUSTED" in message or "429" in message:
        return (
            "quota_exhausted",
            True,
            429,
            "The language-model quota is exhausted. Retry later or use an API project with available quota.",
        )
    if isinstance(exc, httpx.ConnectError) or "nodename nor servname" in message:
        return (
            "connection_failed",
            True,
            503,
            "Cannot reach the language-model provider. Check your Internet connection, DNS, or firewall, then retry.",
        )
    return (
        "provider_failed",
        False,
        502,
        "The language-model provider could not process this request. Check the selected model and API key.",
    )


def _project_response(user_id: str, project_id: str, thread_id: str, state: GraphState) -> dict:
    """Return only JSON-safe state needed by the browser interface."""
    ensure_history(state)
    ensure_resource_library(state)
    presentation = state.presentation.model_dump(mode="json") if state.presentation else None
    messages = [turn.model_dump(mode="json") for turn in state.conversation_history]
    resource_messages = [turn.model_dump(mode="json") for turn in state.resource_conversation_history]
    return {
        "user_id": user_id,
        "project_id": project_id,
        "thread_id": thread_id,
        "presentation": presentation,
        "resource_library": [_resource_response(resource) for resource in state.resource_library],
        "resource_analysis": state.resource_analysis.model_dump(mode="json") if state.resource_analysis else None,
        "messages": messages,
        "resource_messages": resource_messages,
        "conversation_context": state.conversation_context.model_dump(mode="json"),
        "evidence_context_mode": state.evidence_context_mode.value,
        "patient_case_mode": state.patient_case_mode,
        "patient_case_acknowledged": state.patient_case_acknowledged,
        "user_profile": state.user_profile.model_dump(mode="json"),
        "last_tool": state.execution.last_tool,
        "workflow_status": (
            state.presentation.state.workflow_status.value if state.presentation is not None else None
        ),
        "error": state.execution.error,
        "required_human_action": _required_human_action(state),
        "workflow": WorkflowViewBuilder.build(
            state,
            get_repository().active_job(user_id, project_id),
        ),
    }


def _resource_response(resource) -> dict[str, object]:
    """Expose resource metadata only; extracted PDF text never leaves the API."""
    return {
        "id": resource.id,
        "filename": resource.filename,
        "title": resource.title,
        "source": resource.source,
        "language": resource.language.value if hasattr(resource.language, "value") else resource.language,
        "file_type": resource.file_type,
        "uploaded_at": resource.uploaded_at.isoformat(),
        "is_validated": resource.is_validated,
        "page_count": len(resource.extracted_pages),
        "characters_extracted": len(resource.extracted_text or ""),
    }


def _required_human_action(state: GraphState) -> dict[str, str] | None:
    """Expose deterministic UI actions only when the workflow requests one."""
    output = state.execution.tool_output or {}
    presentation = state.presentation
    if (
        presentation is not None
        and presentation.state.workflow_status == WorkflowStatus.AWAITING_SLIDE_RESOLUTION
    ):
        slide_number = presentation.state.blocked_slide_number or "?"
        return {
            "action": "resolve_slide_generation",
            "message": (
                f"Slide {slide_number} cannot be generated by AI from the validated PDFs. "
                "Edit the blueprint item, add a relevant PDF, or choose ‘Written by user’."
            ),
        }
    if (
        output.get("error_code") == "RESOURCES_VALIDATION_REQUIRED"
        or WorkflowPolicy.requires_resource_validation(presentation)
    ):
        return {
            "action": "validate_resources",
            "message": "Validate the uploaded resources before generating the blueprint.",
        }
    return None


def _get_project(user_id: str, project_id: str) -> tuple[str, GraphState]:
    stored = get_repository().load(user_id, project_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    thread_id, state = stored
    state.resource_chunks = get_repository().load_resource_chunks(user_id, project_id)
    return thread_id, state


def _authenticated_user(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication is required.")
    user_id = get_repository().user_for_token(authorization.removeprefix("Bearer "))
    if user_id is None:
        raise HTTPException(status_code=401, detail="Your session is invalid or expired. Please sign in again.")
    return user_id


def _assert_owner(user_id: str, authenticated_user: str) -> None:
    if user_id != authenticated_user:
        raise HTTPException(status_code=403, detail="You cannot access another user's projects.")


def _workflow_conflict(exc: ValueError) -> HTTPException:
    """Use a stable error code so web clients do not have to parse human text."""
    if isinstance(exc, DomainError):
        detail = {
            "code": exc.code,
            "message": exc.user_message,
            "retryable": exc.retryable,
        }
    else:
        detail = {
            "code": "WORKFLOW_VALIDATION_FAILED",
            "message": str(exc),
            "retryable": False,
        }
    return HTTPException(status_code=409, detail=detail)


def _audit_payload(state: GraphState, extra: dict[str, object] | None = None) -> dict[str, object]:
    """Store operational metadata without storing secrets or raw PDF content."""
    presentation = state.presentation
    payload: dict[str, object] = {
        "workflow_version": WORKFLOW_VERSION,
        "harness_version": HARNESS_VERSION,
        "retrieval_version": RETRIEVAL_VERSION,
        "workflow_status": presentation.state.workflow_status.value if presentation else None,
        "last_tool": state.execution.last_tool,
        "error": state.execution.error,
        "evidence_context_mode": state.evidence_context_mode.value,
        "patient_case_mode": state.patient_case_mode,
    }
    if presentation and presentation.generation_records:
        payload["last_generation"] = presentation.generation_records[-1].model_dump(mode="json")
    if extra:
        payload.update(extra)
    return payload


def _save_project(
    user_id: str,
    project_id: str,
    thread_id: str,
    state: GraphState,
    *,
    event_type: str = "PROJECT_STATE_SAVED",
    actor: str = "system",
    extra_audit: dict[str, object] | None = None,
) -> dict:
    repository = get_repository()
    ensure_history(state)
    ensure_resource_library(state)
    try:
        repository.save_with_event(
            user_id,
            project_id,
            thread_id,
            state,
            event_type,
            actor,
            _audit_payload(state, extra_audit),
        )
    except DomainError as exc:
        raise _workflow_conflict(exc) from exc
    return _project_response(user_id, project_id, thread_id, state)


@lru_cache
def get_agent() -> HealthcarePresentationAgent:
    """Create the workflow once and reuse it for all API requests."""
    return HealthcarePresentationAgent()


@lru_cache
def get_repository() -> UserSessionRepository:
    return UserSessionRepository()


@app.get("/")
def root():
    """Open the local web interface from the server's base URL."""
    return RedirectResponse(url="/app", status_code=307)


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


@app.get("/app", include_in_schema=False)
def web_app():
    """Serve the local JavaScript interface."""
    return FileResponse(_web_dir / "index.html", media_type="text/html")


app.mount("/web", StaticFiles(directory=_web_dir), name="web")


@app.post("/projects/{user_id}/{project_id}/presentation/setup")
def setup_presentation(
    user_id: str,
    project_id: str,
    request: PresentationSetupRequest,
    authenticated_user: str = Depends(_authenticated_user),
):
    """Create a presentation from explicit human input, without an LLM decision."""
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    if state.presentation is not None:
        raise HTTPException(status_code=409, detail="A presentation already exists for this Project.")
    if state.patient_case_mode:
        try:
            PatientCasePrivacyGuard().ensure_texts_safe((request.topic, request.objective))
        except ValueError as exc:
            raise _workflow_conflict(exc) from exc

    state.user_profile = get_repository().get_user_profile(user_id)
    try:
        state = CollectPresentationContextUseCase().execute(state, **request.model_dump())
        state = ValidatePresentationContextUseCase().execute(state)
        state = CreatePresentationWorkflowUseCase().execute(state)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc

    state.execution = ExecutionContext(last_tool="create_presentation")
    return _save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="PRESENTATION_CREATED_FROM_FORM",
        actor="user",
        extra_audit={
            "topic_length": len(request.topic),
            "objective_length": len(request.objective),
            "duration_minutes": request.duration_minutes,
            "audience": request.audience.value,
            "presentation_type": request.presentation_type.value,
            "language": request.language.value,
        },
    )


@app.post("/chat")
def chat(request: ChatRequest, authenticated_user: str = Depends(_authenticated_user)):
    """Send a user message to the presentation workflow."""
    _assert_owner(request.user_id, authenticated_user)
    stored = get_repository().load(request.user_id, request.project_id)
    thread_id, state = (
        stored
        if stored
        else get_repository().create_empty(request.user_id, request.project_id)
    )
    state.resource_chunks = get_repository().load_resource_chunks(request.user_id, request.project_id)
    if state.patient_case_mode:
        try:
            PatientCasePrivacyGuard().ensure_text_safe(request.message)
        except ValueError as exc:
            raise _workflow_conflict(exc) from exc
    ensure_history(state)
    state.messages.append(HumanMessage(content=request.message))
    add_turn(state, "user", request.message)
    state.user_profile = get_repository().get_user_profile(request.user_id)
    if state.presentation is not None:
        # Keep future blueprint/slide generations aligned with a profile update.
        state.presentation.owner_profile = state.user_profile
    # Persist the user's turn before any provider work. Quota, network, or
    # model failures must never make a submitted message disappear from the
    # durable conversation history.
    _save_project(
        request.user_id,
        request.project_id,
        thread_id,
        state,
        event_type="USER_MESSAGE_RECEIVED",
        actor="user",
        extra_audit={"message_length": len(request.message)},
    )
    try:
        result = get_agent().invoke(state, thread_id=thread_id)
    except Exception as exc:
        logger.exception("Language-model request failed for user=%s project=%s", request.user_id, request.project_id)
        failure_category, retryable, status_code, detail = _provider_failure(exc)
        state.execution = ExecutionContext(
            tool_output={
                "status": "failed",
                "error_code": "LLM_PROVIDER_FAILURE",
                "retryable": retryable,
            },
            error=detail,
        )
        _save_project(
            request.user_id,
            request.project_id,
            thread_id,
            state,
            event_type="AGENT_TURN_FAILED",
            actor="system",
            extra_audit={
                "message_length": len(request.message),
                "failure_category": failure_category,
                "retryable": retryable,
                **_configured_model_identity(),
            },
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
    saved_state = GraphState(**result)
    ensure_history(saved_state)
    last_assistant_message = next(
        (
            _message_text(getattr(message, "content", ""))
            for message in reversed(saved_state.messages)
            if getattr(message, "type", "") == "ai" and _message_text(getattr(message, "content", ""))
        ),
        "",
    )
    if last_assistant_message and (
        not saved_state.conversation_history
        or saved_state.conversation_history[-1].role != "assistant"
        or saved_state.conversation_history[-1].text != last_assistant_message
    ):
        add_turn(saved_state, "assistant", last_assistant_message)
    project_payload = _save_project(
        request.user_id,
        request.project_id,
        thread_id,
        saved_state,
        event_type="AGENT_TURN_COMPLETED",
        actor="llm",
        extra_audit={"message_length": len(request.message), "tool_output": saved_state.execution.tool_output},
    )
    return {
        "thread_id": thread_id,
        "project_id": request.project_id,
        "message": last_assistant_message,
        "last_tool": saved_state.execution.last_tool,
        "error": saved_state.execution.error,
        "presentation": saved_state.presentation.model_dump(mode="json") if saved_state.presentation else None,
        "project": project_payload,
    }


@app.post("/resources/pdf/{user_id}/{project_id}")
async def upload_pdf_resource(user_id: str, project_id: str, file: UploadFile = File(...), authenticated_user: str = Depends(_authenticated_user)):
    """Extract a PDF into the Project library; production selection is explicit."""
    _assert_owner(user_id, authenticated_user)
    filename = Path(file.filename or "resource.pdf").name
    # Some browsers/local proxies send application/octet-stream for a valid
    # PDF. The extension is accepted here; PyMuPDF below remains the actual
    # content validation boundary.
    if file.content_type not in {"application/pdf", "application/x-pdf"} and not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF uploads are accepted.")
    stored = get_repository().load(user_id, project_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    thread_id, state = stored
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF files are limited to 20 MB.")
    try:
        resource = ExtractPdfResourceUseCase().execute(
            filename,
            content,
            patient_case_mode=state.patient_case_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ensure_resource_library(state)
    AddProjectResourceUseCase().execute(state, resource)
    state.execution = ExecutionContext()
    _save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="RESOURCE_UPLOADED",
        actor="user",
        extra_audit={"resource_id": resource.id, "filename": resource.filename, "pages": len(resource.extracted_pages)},
    )
    return {"resource_id": resource.id, "filename": resource.filename, "characters_extracted": len(resource.extracted_text or "")}


@app.post("/projects/{user_id}/{project_id}/resources/summary")
def summarize_resources(user_id: str, project_id: str, authenticated_user: str = Depends(_authenticated_user)):
    """Generate a separate, source-only overview to support discussion before production."""
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        ensure_resource_library(state)
        language = state.user_profile.preferred_language
        analysis = SummarizeResourcesUseCase().execute(
            state.resource_library,
            language=language,
            chunks=state.resource_chunks,
            evidence_context_mode=state.evidence_context_mode,
            patient_case_mode=state.patient_case_mode,
        )
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    except Exception as exc:
        logger.exception("Resource analysis failed for user=%s project=%s", user_id, project_id)
        raise HTTPException(status_code=502, detail="The model could not analyze the uploaded resources. Please retry.") from exc
    state.resource_analysis = analysis
    return _save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="RESOURCE_ANALYSIS_GENERATED",
        actor="llm",
        extra_audit={"resource_ids": analysis.resource_ids},
    )


@app.post("/projects/{user_id}/{project_id}/resources/discuss")
def discuss_resources(
    user_id: str,
    project_id: str,
    request: ResourceDiscussionRequest,
    authenticated_user: str = Depends(_authenticated_user),
):
    """Discuss project PDFs independently from the presentation workflow."""
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    ensure_resource_library(state)
    if state.patient_case_mode:
        try:
            PatientCasePrivacyGuard().ensure_text_safe(request.question)
        except ValueError as exc:
            raise _workflow_conflict(exc) from exc
    # The resource workspace has its own durable transcript. Persist the user
    # question before provider work so a failed analysis cannot erase it.
    add_resource_turn(state, "user", request.question)
    _save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="RESOURCE_DISCUSSION_MESSAGE_RECEIVED",
        actor="user",
        extra_audit={"question_length": len(request.question)},
    )
    try:
        answer = DiscussResourcesUseCase().execute(
            state.resource_library,
            request.question,
            language=state.user_profile.preferred_language,
            chunks=state.resource_chunks,
            evidence_context_mode=state.evidence_context_mode,
            patient_case_mode=state.patient_case_mode,
        )
    except ValueError as exc:
        state.execution = ExecutionContext(error=str(exc))
        _save_project(
            user_id,
            project_id,
            thread_id,
            state,
            event_type="RESOURCE_DISCUSSION_REJECTED",
            actor="system",
            extra_audit={"question_length": len(request.question)},
        )
        raise _workflow_conflict(exc) from exc
    except Exception as exc:
        logger.exception("Resource discussion failed for user=%s project=%s", user_id, project_id)
        failure_category, retryable, status_code, detail = _provider_failure(exc)
        state.execution = ExecutionContext(
            tool_output={
                "status": "failed",
                "error_code": "LLM_PROVIDER_FAILURE",
                "retryable": retryable,
            },
            error=detail,
        )
        _save_project(
            user_id,
            project_id,
            thread_id,
            state,
            event_type="RESOURCE_DISCUSSION_FAILED",
            actor="system",
            extra_audit={
                "question_length": len(request.question),
                "failure_category": failure_category,
                "retryable": retryable,
                **_configured_model_identity(),
            },
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
    add_resource_turn(state, "assistant", answer)
    return _save_project(
        user_id, project_id, thread_id, state,
        event_type="RESOURCE_DISCUSSION_COMPLETED", actor="llm",
        extra_audit={"resource_count": len(state.resource_library), "question_length": len(request.question)},
    )


@app.post("/projects/{user_id}/{project_id}/resources/validate")
def approve_resources(user_id: str, project_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = validate_resources.func(state)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    state.execution = ExecutionContext()
    return _save_project(user_id, project_id, thread_id, state, event_type="RESOURCES_VALIDATED", actor="user")


@app.delete("/projects/{user_id}/{project_id}/resources/{resource_id}")
def delete_resource(
    user_id: str,
    project_id: str,
    resource_id: str,
    authenticated_user: str = Depends(_authenticated_user),
):
    """Remove a PDF and safely reset content that could depend on it."""
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        ensure_resource_library(state)
        RemoveProjectResourceUseCase().execute(state, resource_id)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="RESOURCE_DELETED",
        actor="user",
        extra_audit={"resource_id": resource_id},
    )


@app.post("/projects/{user_id}/{project_id}/resources/{resource_id}/attach")
def attach_resource_to_presentation(
    user_id: str, project_id: str, resource_id: str, authenticated_user: str = Depends(_authenticated_user)
):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        ensure_resource_library(state)
        AttachResourceToPresentationUseCase().execute(state, resource_id)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    state.execution = ExecutionContext()
    return _save_project(user_id, project_id, thread_id, state, event_type="RESOURCE_ATTACHED_TO_PRESENTATION", actor="user", extra_audit={"resource_id": resource_id})


@app.delete("/projects/{user_id}/{project_id}/resources/{resource_id}/attach")
def detach_resource_from_presentation(
    user_id: str, project_id: str, resource_id: str, authenticated_user: str = Depends(_authenticated_user)
):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        DetachResourceFromPresentationUseCase().execute(state, resource_id)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    state.execution = ExecutionContext()
    return _save_project(user_id, project_id, thread_id, state, event_type="RESOURCE_DETACHED_FROM_PRESENTATION", actor="user", extra_audit={"resource_id": resource_id})


@app.post("/projects/{user_id}/{project_id}/blueprint/items/{index}/approve")
def approve_blueprint_item(user_id: str, project_id: str, index: int, request: ReviewRequest, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = ReviewBlueprintItemUseCase().execute(state, index, request.comments)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(user_id, project_id, thread_id, state, event_type="BLUEPRINT_ITEM_APPROVED", actor="user", extra_audit={"item_index": index})


@app.post("/projects/{user_id}/{project_id}/blueprint/items/{index}/reject")
def reject_blueprint_item(user_id: str, project_id: str, index: int, request: ReviewRequest, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = RejectBlueprintItemUseCase().execute(state, index, request.comments)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(user_id, project_id, thread_id, state, event_type="BLUEPRINT_ITEM_REJECTED", actor="user", extra_audit={"item_index": index})


@app.put("/projects/{user_id}/{project_id}/blueprint/items/{index}")
def edit_blueprint_item(
    user_id: str,
    project_id: str,
    index: int,
    request: BlueprintItemEditRequest,
    authenticated_user: str = Depends(_authenticated_user),
):
    """Save direct user-authored or user-edited blueprint content."""
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = EditBlueprintItemUseCase().execute(state, index, **request.model_dump())
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="BLUEPRINT_ITEM_EDITED_BY_USER",
        actor="user",
        extra_audit={"item_index": index, "content_origin": request.content_origin},
    )


@app.post("/projects/{user_id}/{project_id}/blueprint/approve")
def approve_blueprint(user_id: str, project_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = validate_blueprint.func(state, approved=True)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(user_id, project_id, thread_id, state, event_type="BLUEPRINT_APPROVED", actor="user")


@app.put("/projects/{user_id}/{project_id}/agenda")
def update_agenda(user_id: str, project_id: str, request: AgendaRequest, authenticated_user: str = Depends(_authenticated_user)):
    """Save a human edit of the model-proposed agenda."""
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    if state.presentation is None or state.presentation.agenda is None:
        raise HTTPException(status_code=409, detail="Generate a blueprint before editing the agenda.")
    try:
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.AWAITING_AGENDA_APPROVAL,),
            "edit the agenda",
        )
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    items = [item.strip() for item in request.items if item.strip()]
    if not items:
        raise HTTPException(status_code=422, detail="Agenda must contain at least one item.")
    state.presentation.agenda.items = items
    state.presentation.agenda.reviewer_comments = request.comments.strip() or None
    state.presentation.agenda.is_validated = False
    state.presentation.blueprint.is_validated = False
    state.presentation.state.blueprint_validated = False
    state.presentation.state.slides_validated = False
    state.presentation.state.presentation_validated = False
    state.presentation.state.workflow_status = WorkflowStatus.AWAITING_AGENDA_APPROVAL
    return _save_project(user_id, project_id, thread_id, state, event_type="AGENDA_UPDATED", actor="user")


@app.post("/projects/{user_id}/{project_id}/agenda/approve")
def approve_agenda(user_id: str, project_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    if state.presentation is None or state.presentation.agenda is None or not state.presentation.agenda.items:
        raise HTTPException(status_code=409, detail="Generate an agenda before approving it.")
    try:
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.AWAITING_AGENDA_APPROVAL,),
            "approve the agenda",
        )
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    state.presentation.agenda.is_validated = True
    state.presentation.state.workflow_status = WorkflowStatus.AWAITING_BLUEPRINT_APPROVAL
    return _save_project(user_id, project_id, thread_id, state, event_type="AGENDA_APPROVED", actor="user")


@app.put("/projects/{user_id}/{project_id}/theme")
def update_theme(user_id: str, project_id: str, request: ThemeRequest, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    if state.presentation is None:
        raise HTTPException(status_code=409, detail="Create a presentation before selecting a theme.")
    if request.custom_template_id:
        if get_repository().presentation_template_path(user_id, request.custom_template_id) is None:
            raise HTTPException(status_code=404, detail="Custom template not found.")
        state.presentation.custom_template_id = request.custom_template_id
    elif request.theme is not None:
        state.presentation.theme = request.theme
        state.presentation.custom_template_id = None
    else:
        raise HTTPException(status_code=422, detail="Select a built-in or custom template.")
    return _save_project(user_id, project_id, thread_id, state, event_type="PRESENTATION_THEME_SELECTED", actor="user")


@app.put("/projects/{user_id}/{project_id}/evidence-settings")
def update_project_evidence_settings(
    user_id: str,
    project_id: str,
    request: ProjectEvidenceSettingsRequest,
    authenticated_user: str = Depends(_authenticated_user),
):
    """Persist human-controlled retrieval and patient-case privacy settings."""
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = UpdateProjectEvidenceSettingsUseCase().execute(state, **request.model_dump())
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="PROJECT_EVIDENCE_SETTINGS_UPDATED",
        actor="user",
        extra_audit={
            "evidence_context_mode": state.evidence_context_mode.value,
            "patient_case_mode": state.patient_case_mode,
        },
    )


@app.put("/projects/{user_id}/{project_id}/presentation/details")
def update_presentation_details(
    user_id: str,
    project_id: str,
    request: PresentationDetailsRequest,
    authenticated_user: str = Depends(_authenticated_user),
):
    """Save human-supplied title-slide metadata without involving the LLM."""
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = UpdatePresentationDetailsUseCase().execute(state, **request.model_dump())
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="PRESENTATION_DETAILS_UPDATED",
        actor="user",
        extra_audit={"fields": [key for key, value in request.model_dump().items() if value.strip()]},
    )


@app.post("/projects/{user_id}/{project_id}/blueprint/regenerate")
def regenerate_blueprint(user_id: str, project_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = RegenerateBlueprintUseCase().execute(state)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(user_id, project_id, thread_id, state, event_type="BLUEPRINT_REGENERATED", actor="llm")


@app.post("/projects/{user_id}/{project_id}/slides/{index}/approve")
def approve_slide(user_id: str, project_id: str, index: int, request: ReviewRequest, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = ReviewSlideUseCase().execute(state, index, request.comments)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(user_id, project_id, thread_id, state, event_type="SLIDE_APPROVED", actor="user", extra_audit={"slide_index": index})


@app.post("/projects/{user_id}/{project_id}/slides/{index}/reject")
def reject_slide(user_id: str, project_id: str, index: int, request: ReviewRequest, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = RejectSlideUseCase().execute(state, index, request.comments)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(user_id, project_id, thread_id, state, event_type="SLIDE_REJECTED", actor="user", extra_audit={"slide_index": index})


@app.put("/projects/{user_id}/{project_id}/slides/{index}")
def edit_slide(
    user_id: str,
    project_id: str,
    index: int,
    request: SlideEditRequest,
    authenticated_user: str = Depends(_authenticated_user),
):
    """Save direct slide edits while retaining the original model snapshot."""
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = EditSlideUseCase().execute(state, index, **request.model_dump())
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="SLIDE_EDITED_BY_USER",
        actor="user",
        extra_audit={"slide_index": index, "content_origin": request.content_origin},
    )


@app.post("/projects/{user_id}/{project_id}/slides/{index}/regenerate")
def regenerate_slide(user_id: str, project_id: str, index: int, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = RegenerateSlideUseCase().execute(state, index)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(user_id, project_id, thread_id, state, event_type="SLIDE_REGENERATED", actor="llm", extra_audit={"slide_index": index})


@app.post("/projects/{user_id}/{project_id}/slides/approve")
def approve_slides(user_id: str, project_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = validate_slides.func(state, approved=True)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(user_id, project_id, thread_id, state, event_type="SLIDES_APPROVED", actor="user")


@app.post("/projects/{user_id}/{project_id}/presentation/approve")
def approve_final_presentation(user_id: str, project_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = validate_final_presentation.func(state, approved=True)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(user_id, project_id, thread_id, state, event_type="PRESENTATION_APPROVED", actor="user")


@app.get("/presentations/{user_id}/{project_id}/export/pptx")
def export_powerpoint(user_id: str, project_id: str, authenticated_user: str = Depends(_authenticated_user)):
    """Download the generated presentation as a PowerPoint file."""
    _assert_owner(user_id, authenticated_user)
    stored = get_repository().load(user_id, project_id)
    if stored is None or stored[1].presentation is None:
        raise HTTPException(status_code=404, detail="Presentation not found.")
    thread_id, state = stored
    try:
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.READY_FOR_EXPORT, WorkflowStatus.EXPORTED),
            "export the presentation",
        )
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    try:
        custom_template = (
            get_repository().presentation_template_path(user_id, state.presentation.custom_template_id)
            if state.presentation.custom_template_id
            else None
        )
        path = ExportPowerPointUseCase().execute(
            state.presentation,
            _exports_dir,
            custom_template,
            resolve_presentation_resources(state),
        )
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    state.presentation.state.workflow_status = WorkflowStatus.EXPORTED
    _save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="PRESENTATION_EXPORTED",
        actor="user",
        extra_audit={"filename": path.name},
    )
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", filename=f"{state.presentation.title}.pptx")


from app.interfaces.api.routers import auth, jobs, platform, projects  # noqa: E402

# Versioned platform and asynchronous workload endpoints are isolated from the
# legacy compatibility routes above.  More domains can migrate incrementally
# without changing the public URLs used by the two local interfaces.
app.include_router(platform.router)
app.include_router(jobs.router)
app.include_router(auth.router)
app.include_router(projects.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
