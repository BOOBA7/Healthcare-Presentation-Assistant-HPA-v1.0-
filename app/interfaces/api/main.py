from app.application.services.presentation_context_policy import PresentationContextPolicy
from app.domain.models.professional_scope_declaration import ProfessionalScopeDeclaration
from functools import lru_cache
import logging
from io import BytesIO
from pathlib import Path

import httpx
from fastapi import Request, Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from app.interfaces.api.memory_upload import read_pdf_upload
from app.application.services.source_screening import SourceScreening
from app.application.services.source_date_policy import SourceDatePolicy
from app.application.services.source_document import SourceDocument
from app.domain.exceptions.workflow_error import WorkflowError
from fastapi.responses import Response
from urllib.parse import quote
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, ConfigDict

from app.application.services.prototype_policy import PrototypePolicy
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
    RecordProfessionalScopeUseCase,
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
    EditBlueprintItemUseCase,
    EditSlideUseCase,
    AuthorSlideFromBlueprintUseCase,
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


@app.exception_handler(RequestValidationError)
async def safe_ocr_validation_error(request, exc):
    if (request.url.path.endswith("/ocr-review") or "/asset-review" in request.url.path
            or "/assets/" in request.url.path or request.url.path.endswith("/asset-original")):
        return JSONResponse(status_code=422, content={"detail": "Invalid extraction-review request."})
    return await request_validation_exception_handler(request, exc)


@app.middleware("http")
async def prototype_input_boundary(request: Request, call_next):
    # Account credentials are not presentation content and must never be inspected here.
    path = request.url.path
    if request.method in {"POST", "PUT", "PATCH"} and (
        "/projects" in path or "/chat" in path or "/conversations" in path
    ) and "application/json" in request.headers.get("content-type", ""):
        try:
            PrototypePolicy.screen(await request.json())
        except DomainError as exc:
            return JSONResponse(status_code=409, content={"detail": {"code": exc.code, "message": exc.user_message}})
        except ValueError:
            return JSONResponse(status_code=422, content={"detail": "Invalid JSON."})
    return await call_next(request)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    user_id: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=128)


class ProjectRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=128)
    project_name: str | None = Field(default=None, min_length=1, max_length=128)
    prototype_declaration: str | None = None
    external_processing_acknowledged: bool = False


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


class BlueprintRegenerationRequest(BaseModel):
    """Reviewer feedback to persist before an asynchronous blueprint revision."""

    comments_by_index: dict[int, str] = Field(default_factory=dict)


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


class ProfessionalScopeDeclarationRequest(BaseModel):
    """Explicit human declaration required for a profile/audience mismatch."""

    declared_role: str = Field(min_length=3, max_length=200)
    delivery_purpose: str = Field(min_length=12, max_length=1_000)
    confirmed_within_scope: bool


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
    duration_minutes: int = Field(strict=True, gt=0, le=480)
    objective: str = Field(min_length=1, max_length=4_000)
    target_slide_count: int = Field(strict=True, gt=0, le=200)
    special_instructions: str = Field(min_length=1, max_length=4000)
    professional_scope: str = Field(min_length=12, max_length=1000)
    is_multidisciplinary: bool = Field(strict=True)
    confirmed_within_scope: bool = Field(strict=True)
    confirmed_multidisciplinary: bool = Field(default=False, strict=True)
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
    presentation = state.presentation.model_dump(mode="json", exclude={"resources": {"__all__": {"metadata": {"assets": {"__all__": {"content_base64"}}}}}}) if state.presentation else None
    messages = [turn.model_dump(mode="json") for turn in state.conversation_history]
    resource_messages = [turn.model_dump(mode="json") for turn in state.resource_conversation_history]
    return {
        "user_id": user_id,
        "project_id": project_id,
        "thread_id": thread_id,
        "presentation": presentation,
        "resource_library": [_resource_response(resource) for resource in state.resource_library],
        "owner_library": [_resource_response(resource) for resource in get_repository().list_library_resources(user_id)],
        "resource_analysis": state.resource_analysis.model_dump(mode="json") if state.resource_analysis else None,
        "messages": messages,
        "resource_messages": resource_messages,
        "conversation_context": state.conversation_context.model_dump(mode="json"),
        "evidence_context_mode": state.evidence_context_mode.value,
        "prototype_declaration": state.prototype_declaration,
        "prototype_policy_version": PrototypePolicy.VERSION,
        "external_processing_disclosure": PrototypePolicy.DISCLOSURE,
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
    """Expose source descriptors only; no raw extraction or embedded metadata."""
    try:
        date_evidence = SourceDatePolicy.require(resource, allow_unconfirmed=True).model_dump(mode="json")
        from app.application.services.ocr_review import is_reviewed
        date_blocker = ({"code": "OCR_CONFIRMATION_REQUIRED", "message": "Review every OCR region against its original before using this source."}
                        if resource.metadata.ocr_engine and not is_reviewed(resource) else None)
        from app.application.services.source_assets import is_reviewed as assets_reviewed
        if date_blocker is None and resource.metadata.assets and not assets_reviewed(resource):
            date_blocker = {"code": "ASSET_CONFIRMATION_REQUIRED", "message": "Review extracted images and tables against their original."}
    except DomainError as exc:
        date_evidence = None
        date_blocker = {"code": exc.code, "message": exc.user_message}
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
        "location_kind": "slide" if resource.file_type.value == "pptx" else "page",
        "asset_inventory": [
            {"id": asset.id, "kind": asset.kind, "media_type": asset.media_type,
             "location": asset.location.model_dump(mode="json"), "review_status": asset.review_status}
            for asset in resource.metadata.assets
        ],
        "characters_extracted": len(resource.extracted_text or ""),
        "scientific_date": date_evidence,
        "source_blocker": date_blocker,
        "original_available": resource._original_content is not None,
        "original_sha256": resource.metadata.original_sha256,
        "media_type": resource.metadata.media_type,
        "ocr_pending": bool(resource.metadata.ocr_engine) and not bool(resource.metadata.ocr_reviews),
        "ocr_reviewed": bool(resource.metadata.ocr_reviews),
        "ocr_region_count": len(resource.metadata.ocr_regions),
        "author": resource.metadata.author,
        "publisher": resource.metadata.publisher,
        "rights": resource.metadata.rights,
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


def _require_prototype_input(value):
    try:
        PrototypePolicy.screen(value)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc


def _require_prototype(state):
    try:
        PrototypePolicy.state(state)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc


def _get_project(user_id: str, project_id: str, *, require_prototype: bool = True, require_context: bool = True) -> tuple[str, GraphState]:
    stored = get_repository().load(user_id, project_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    thread_id, state = stored
    if require_prototype:
        _require_prototype(state)
        if require_context:
            try:
                PresentationContextPolicy.require(state.presentation)
            except ValueError as exc:
                raise _workflow_conflict(exc) from exc
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
        "prototype_declaration": state.prototype_declaration,
        "prototype_policy_version": PrototypePolicy.VERSION,
        "external_processing_disclosure": PrototypePolicy.DISCLOSURE,
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
    _require_prototype_input(request)
    thread_id, state = _get_project(user_id, project_id, require_context=False)
    existing = state.presentation
    if existing is not None:
        # This slice completes legacy context only; substantive editing/invalidation is deferred.
        try:
            PresentationContextPolicy.require(existing)
        except ValueError:
            pass
        else:
            raise HTTPException(status_code=409, detail="Presentation context is already complete.")
        for field, value in existing.context.model_dump().items():
            if value is not None and getattr(request, field, value) != value:
                raise HTTPException(status_code=409, detail=f"Preserve existing context field: {field}")
    if (not request.confirmed_within_scope or not request.professional_scope.strip()
            or len(request.professional_scope.strip()) < 12
            or (request.is_multidisciplinary and not request.confirmed_multidisciplinary)):
        raise HTTPException(status_code=409, detail="Explicit scope and multidisciplinary competence confirmation required.")
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

    if existing is not None:
        existing.context = state.presentation_context
        existing.state.context = state.presentation_context
    declaration = ProfessionalScopeDeclaration(
        declared_role=state.user_profile.professional_role,
        delivery_purpose=request.professional_scope.strip(),
        confirmed_within_scope=True,
        actor_user_id=authenticated_user,
        context_digest=PresentationContextPolicy.digest(state.presentation.context),
        is_multidisciplinary=request.is_multidisciplinary,
        confirmed_multidisciplinary=request.confirmed_multidisciplinary,
    )
    state.presentation.professional_scope_declaration = declaration
    state.execution = ExecutionContext(last_tool="create_presentation")
    return _save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="PRESENTATION_CONTEXT_COMPLETED" if existing else "PRESENTATION_CREATED_FROM_FORM",
        actor="user",
        extra_audit={
            "actor_user_id": authenticated_user,
            "approval": True,
            "context_digest": declaration.context_digest,
            "confirmed_within_scope": True,
            "is_multidisciplinary": request.is_multidisciplinary,
            "confirmed_multidisciplinary": request.confirmed_multidisciplinary,
            "declared_at": declaration.declared_at.isoformat(),
            "target_slide_count": request.target_slide_count,
            "topic_length": len(request.topic),
            "objective_length": len(request.objective),
            "duration_minutes": request.duration_minutes,
            "audience": request.audience.value,
            "presentation_type": request.presentation_type.value,
            "language": request.language.value,
        },
    )


@app.post("/projects/{user_id}/{project_id}/presentation/scope-clarification")
def record_professional_scope_declaration(
    user_id: str,
    project_id: str,
    request: ProfessionalScopeDeclarationRequest,
    authenticated_user: str = Depends(_authenticated_user),
):
    """Resolve a scope mismatch through explicit, durable human input only."""
    _assert_owner(user_id, authenticated_user)
    _require_prototype_input(request)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = RecordProfessionalScopeUseCase().execute(state, **request.model_dump())
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    state.execution = ExecutionContext(last_tool="record_professional_scope_declaration")
    return _save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="PROFESSIONAL_SCOPE_DECLARED",
        actor="user",
        extra_audit={
            "actor_user_id": authenticated_user,
            "approval": True,
            "declared_role": request.declared_role.strip(),
            "confirmed_within_scope": request.confirmed_within_scope,
        },
    )


@app.post("/chat")
def chat(request: ChatRequest, authenticated_user: str = Depends(_authenticated_user)):
    """Send a user message to the presentation workflow."""
    _assert_owner(request.user_id, authenticated_user)
    _require_prototype_input(request)
    stored = get_repository().load(request.user_id, request.project_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Create a Project and declare public/synthetic content first.")
    thread_id, state = stored
    _require_prototype(state)
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


@app.post("/resources/{user_id}/{project_id}")
@app.post("/resources/pdf/{user_id}/{project_id}")
async def upload_pdf_resource(user_id: str, project_id: str, request: Request, authenticated_user: str = Depends(_authenticated_user)):
    """Screen PDF/PNG/JPEG/PPTX into the library; OCR remains pending review."""
    _assert_owner(user_id, authenticated_user)
    stored = get_repository().load(user_id, project_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    thread_id, state = stored
    _require_prototype(state)
    original_filename, media_type, content = await read_pdf_upload(request)
    filename = Path(original_filename).name
    # The shared reader checks the package and filename independently of MIME.
    if (media_type not in {"application/pdf", "application/x-pdf", "image/png", "image/jpeg", "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
            and not filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".pptx"))):
        raise HTTPException(status_code=415, detail="Only PDF, PNG, JPEG and PPTX uploads are accepted.")
    try:
        # Inspect the supplied name before basename normalization can discard it.
        from app.application.services.raster_privacy import screen_raster_text
        screen_raster_text(original_filename)
        resource = ExtractPdfResourceUseCase().execute(
            filename,
            content,
            patient_case_mode=state.patient_case_mode,
            prototype_declaration=state.prototype_declaration,
        )
        extensions = {"pdf": (".pdf",), "png": (".png",), "jpeg": (".jpg", ".jpeg"), "pptx": (".pptx",)}
        if not filename.lower().endswith(extensions[resource.file_type.value]):
            raise WorkflowError("SOURCE_FORMAT_MISMATCH", "The filename does not match the detected source format.")
        ensure_resource_library(state)
        AddProjectResourceUseCase().execute(state, resource)
    except DomainError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.user_message}) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    state.execution = ExecutionContext()
    _save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="RESOURCE_UPLOADED",
        actor="user",
        extra_audit={"resource_id": resource.id, "filename": resource.filename, "pages": len(resource.extracted_pages), "screening_policy": SourceScreening.VERSION,
                     "original_sha256": resource.metadata.original_sha256, "date_policy": SourceDatePolicy.VERSION,
                     "scientific_date": resource.metadata.scientific_date.value, "date_origin": resource.metadata.scientific_date.origin,
                     "ocr_engine": resource.metadata.ocr_engine, "ocr_pending": bool(resource.metadata.ocr_engine)},
    )
    return {"resource_id": resource.id, "filename": resource.filename, "characters_extracted": len(resource.extracted_text or "")}


@app.get("/users/{user_id}/resources")
def owner_library(user_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    return {"resources": [_resource_response(resource) for resource in get_repository().list_library_resources(user_id)]}


@app.post("/projects/{user_id}/{project_id}/library/{resource_id}")
def add_library_source(user_id: str, project_id: str, resource_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    thread, state = _get_project(user_id, project_id, require_context=False)
    resource = get_repository().library_resource(user_id, resource_id)
    if resource is None:
        raise HTTPException(404, "Library resource not found.")
    try:
        AddProjectResourceUseCase().execute(state, resource)
        return _save_project(user_id, project_id, thread, state, event_type="LIBRARY_SOURCE_ADDED", actor=authenticated_user, extra_audit={"resource_id": resource_id})
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc


@app.delete("/users/{user_id}/resources/{resource_id}")
def delete_library_source(user_id: str, resource_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    try:
        result = get_repository().permanently_delete_source(user_id, resource_id, authenticated_user)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    if result is None:
        raise HTTPException(404, "Library resource not found.")
    return JSONResponse(result, status_code=202 if result["cleanup_pending"] else 200)


@app.get("/projects/{user_id}/{project_id}/resources/{resource_id}/original")
def original_pdf(user_id: str, project_id: str, resource_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    _, state = _get_project(user_id, project_id, require_context=False)
    resource = next((item for item in state.resource_library if item.id == resource_id), None)
    if resource is None or resource._original_content is None:
        raise HTTPException(404, "The original PDF is unavailable. Replace this legacy resource.")
    try:
        content = SourceDocument.verify(resource, resource._original_content)
    except DomainError as exc:
        raise _workflow_conflict(exc) from None
    return Response(content, media_type=resource.metadata.media_type or "application/pdf", headers={
        "Content-Disposition": "attachment; filename*=UTF-8''" + quote(resource.filename, safe=""),
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })


class AssetReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)
    values: list[dict[str, str | None]] = Field(min_length=1, max_length=200)
    confirmed_assets: list[str] = Field(min_length=1, max_length=200)


def _asset_source(user_id, resource_id, authenticated_user):
    _assert_owner(user_id, authenticated_user)
    resource = get_repository().library_resource(user_id, resource_id)
    if resource is None or not resource.metadata.assets:
        raise HTTPException(404, "Extracted source items not found.")
    try:
        SourceDocument.verify(resource, resource._original_content)
    except DomainError as exc:
        raise _workflow_conflict(exc) from None
    return resource


@app.post("/users/{user_id}/resources/{resource_id}/asset-review/prepare")
def prepare_asset_review(user_id: str, resource_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    try:
        return get_repository().prepare_asset_review(authenticated_user, resource_id)
    except DomainError as exc:
        raise _workflow_conflict(exc) from None


@app.get("/users/{user_id}/resources/{resource_id}/asset-review")
def get_asset_review(user_id: str, resource_id: str, authenticated_user: str = Depends(_authenticated_user)):
    from app.application.services.source_assets import FIELDS
    resource = _asset_source(user_id, resource_id, authenticated_user)
    return JSONResponse({"resource_id": resource_id, "original_sha256": resource.metadata.original_sha256,
        "scientific_date": resource.metadata.scientific_date.model_dump(mode="json"),
        "revision": max((row.revision for row in resource.metadata.asset_reviews), default=0),
        "assets": [{**asset.model_dump(mode="json", exclude={"content_base64"}),
                    "values": {name: getattr(asset, name) for name in FIELDS}}
                   for asset in resource.metadata.assets],
        "history": [row.model_dump(mode="json") for row in resource.metadata.asset_reviews]},
        headers={"Cache-Control": "no-store"})


@app.get("/users/{user_id}/resources/{resource_id}/assets/{asset_id}")
def get_asset_content(user_id: str, resource_id: str, asset_id: str, original_region: bool = False,
                      authenticated_user: str = Depends(_authenticated_user)):
    from app.application.services.source_assets import asset_content
    resource = _asset_source(user_id, resource_id, authenticated_user)
    try:
        content, media = asset_content(resource, asset_id, original_region=original_region)
    except DomainError as exc:
        raise _workflow_conflict(exc) from None
    return Response(content, media_type=media, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.get("/users/{user_id}/resources/{resource_id}/asset-original")
def get_asset_original(user_id: str, resource_id: str, authenticated_user: str = Depends(_authenticated_user)):
    resource = _asset_source(user_id, resource_id, authenticated_user)
    return Response(resource._original_content, media_type=resource.metadata.media_type,
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                             "Content-Disposition": "attachment; filename*=UTF-8''" + quote(resource.filename, safe="")})


@app.post("/users/{user_id}/resources/{resource_id}/asset-review")
def confirm_asset_review(user_id: str, resource_id: str, request: AssetReviewRequest,
                         authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    try:
        return get_repository().review_assets(authenticated_user, resource_id, request.expected_revision,
                                              request.values, request.confirmed_assets)
    except DomainError as exc:
        raise _workflow_conflict(exc) from None


class OcrReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)
    values: list[str] = Field(min_length=1, max_length=10000)
    confirmed_regions: list[int] = Field(min_length=1, max_length=10000)


def _review_source(user_id, resource_id, authenticated_user):
    _assert_owner(user_id, authenticated_user)
    resource = get_repository().library_resource(user_id, resource_id)
    if resource is None or not resource.metadata.ocr_regions:
        raise HTTPException(404, "OCR source not found.")
    try:
        SourceDocument.verify(resource, resource._original_content)
    except DomainError as exc:
        raise _workflow_conflict(exc) from None
    return resource


@app.get("/users/{user_id}/resources/{resource_id}/ocr-review")
def get_ocr_review(user_id: str, resource_id: str, authenticated_user: str = Depends(_authenticated_user)):
    resource = _review_source(user_id, resource_id, authenticated_user)
    history = resource.metadata.ocr_reviews
    revision = max((review.batch for review in history), default=0)
    latest = {review.region_index: review for review in history if review.batch == revision}
    return JSONResponse({"resource_id": resource_id, "revision": revision,
        "original_sha256": resource.metadata.original_sha256,
        "regions": [{"index": index, "page": region.page, "box": region.box,
                     "extracted_value": region.text, "confidence": region.confidence,
                     "value": latest[index].corrected_value if index in latest else region.text,
                     "review": latest[index].model_dump(mode="json") if index in latest else None}
                    for index, region in enumerate(resource.metadata.ocr_regions)]},
        headers={"Cache-Control": "no-store"})


@app.get("/users/{user_id}/resources/{resource_id}/ocr-regions/{index}")
def get_ocr_region(user_id: str, resource_id: str, index: int, authenticated_user: str = Depends(_authenticated_user)):
    from app.application.services.ocr_region_preview import region_preview
    resource = _review_source(user_id, resource_id, authenticated_user)
    try:
        content = region_preview(resource, index)
    except DomainError as exc:
        raise _workflow_conflict(exc) from None
    return Response(content, media_type="image/png", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.post("/users/{user_id}/resources/{resource_id}/ocr-review")
def confirm_ocr_review(user_id: str, resource_id: str, request: OcrReviewRequest,
                       authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    try:
        return get_repository().review_ocr(authenticated_user, resource_id, request.expected_revision,
                                           request.values, request.confirmed_regions)
    except DomainError as exc:
        raise _workflow_conflict(exc) from None


@app.post("/projects/{user_id}/{project_id}/resources/summary")
def summarize_resources(user_id: str, project_id: str, authenticated_user: str = Depends(_authenticated_user)):
    """Generate a separate, source-only overview to support discussion before production."""
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id, require_context=False)
    try:
        ensure_resource_library(state)
        language = state.user_profile.preferred_language
        analysis = SummarizeResourcesUseCase().execute(
            state.resource_library,
            language=language,
            chunks=state.resource_chunks,
            evidence_context_mode=state.evidence_context_mode,
            patient_case_mode=state.patient_case_mode,
            prototype_declaration=state.prototype_declaration,
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
    _require_prototype_input(request)
    thread_id, state = _get_project(user_id, project_id, require_context=False)
    ensure_resource_library(state)
    try:
        SourceDatePolicy.require_all(state.resource_library)
    except DomainError as exc:
        raise _workflow_conflict(exc) from None
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
            prototype_declaration=state.prototype_declaration,
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
    thread_id, state = _get_project(user_id, project_id, require_context=False)
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
        event_type="RESOURCE_REMOVED_FROM_PROJECT",
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
    thread_id, state = _get_project(user_id, project_id, require_context=False)
    try:
        DetachResourceFromPresentationUseCase().execute(state, resource_id)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    state.execution = ExecutionContext()
    return _save_project(user_id, project_id, thread_id, state, event_type="RESOURCE_DETACHED_FROM_PRESENTATION", actor="user", extra_audit={"resource_id": resource_id})


@app.post("/projects/{user_id}/{project_id}/blueprint/items/{index}/approve")
def approve_blueprint_item(user_id: str, project_id: str, index: int, request: ReviewRequest, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    _require_prototype_input(request)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = ReviewBlueprintItemUseCase().execute(state, index, request.comments)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(user_id, project_id, thread_id, state, event_type="BLUEPRINT_ITEM_APPROVED", actor="user", extra_audit={"item_index": index})


@app.post("/projects/{user_id}/{project_id}/blueprint/items/{index}/reject")
def reject_blueprint_item(user_id: str, project_id: str, index: int, request: ReviewRequest, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    _require_prototype_input(request)
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
    _require_prototype_input(request)
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


@app.post("/projects/{user_id}/{project_id}/slides/from-blueprint/{index}/user-authored")
def author_blocked_slide(
    user_id: str,
    project_id: str,
    index: int,
    authenticated_user: str = Depends(_authenticated_user),
):
    """Resolve one evidence-blocked outline with explicitly user-authored content."""
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = AuthorSlideFromBlueprintUseCase().execute(state, index)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="BLOCKED_SLIDE_AUTHORED_BY_USER",
        actor="user",
        extra_audit={"blueprint_item_index": index},
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
    _require_prototype_input(request)
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
    _require_prototype_input(request)
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
    _require_prototype_input(request)
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
    _require_prototype_input(request)
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


@app.post("/projects/{user_id}/{project_id}/slides/{index}/approve")
def approve_slide(user_id: str, project_id: str, index: int, request: ReviewRequest, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    _require_prototype_input(request)
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = ReviewSlideUseCase().execute(state, index, request.comments)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    return _save_project(user_id, project_id, thread_id, state, event_type="SLIDE_APPROVED", actor="user", extra_audit={"slide_index": index})


@app.post("/projects/{user_id}/{project_id}/slides/{index}/reject")
def reject_slide(user_id: str, project_id: str, index: int, request: ReviewRequest, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    _require_prototype_input(request)
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
    _require_prototype_input(request)
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
        output = BytesIO()
        ExportPowerPointUseCase().execute(
            state.presentation,
            output,
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
        extra_audit={"delivery": "memory_download"},
    )
    return Response(output.getvalue(), media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(state.presentation.title, safe='')}.pptx", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


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

    uvicorn.run(app, host=settings.local_bind_host, port=8000)
