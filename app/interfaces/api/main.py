from functools import lru_cache
import io
import logging
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.ai.agents.healthcare_presentation_agent import HealthcarePresentationAgent
from app.ai.workflows.graph_state import GraphState
from app.application.use_cases.export_powerpoint import ExportPowerPointUseCase
from app.application.use_cases.extract_pdf_resource import ExtractPdfResourceUseCase
from app.application.use_cases.summarize_resources import SummarizeResourcesUseCase
from app.application.use_cases.discuss_resources import DiscussResourcesUseCase
from app.application.use_cases.manage_project_resources import (
    AddProjectResourceUseCase,
    AttachResourceToPresentationUseCase,
    DetachResourceFromPresentationUseCase,
    RemoveProjectResourceUseCase,
)
from app.application.services.workflow_policy import WorkflowPolicy
from app.application.services.conversation_history import add_turn, ensure_history
from app.application.services.resource_library import ensure_resource_library, resolve_presentation_resources
from app.core.config import get_settings
from app.core.versioning import HARNESS_VERSION, RETRIEVAL_VERSION, WORKFLOW_VERSION
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.interfaces.api.job_runner import submit as submit_job
from app.application.services.observability import snapshot as observability_snapshot, record as record_observability
from app.domain.models.user_profile import UserProfile
from app.domain.enums.presentation_theme import PresentationTheme
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.exceptions.domain_error import DomainError
from app.domain.models.execution_context import ExecutionContext
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


def _project_response(user_id: str, project_id: str, thread_id: str, state: GraphState) -> dict:
    """Return only JSON-safe state needed by the browser interface."""
    ensure_history(state)
    ensure_resource_library(state)
    presentation = state.presentation.model_dump(mode="json") if state.presentation else None
    messages = [turn.model_dump(mode="json") for turn in state.conversation_history]
    return {
        "user_id": user_id,
        "project_id": project_id,
        "thread_id": thread_id,
        "presentation": presentation,
        "resource_library": [_resource_response(resource) for resource in state.resource_library],
        "resource_analysis": state.resource_analysis.model_dump(mode="json") if state.resource_analysis else None,
        "messages": messages,
        "conversation_context": state.conversation_context.model_dump(mode="json"),
        "user_profile": state.user_profile.model_dump(mode="json"),
        "last_tool": state.execution.last_tool,
        "workflow_status": (
            state.presentation.state.workflow_status.value if state.presentation is not None else None
        ),
        "error": state.execution.error,
        "required_human_action": _required_human_action(state),
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
    if output.get("error_code") == "RESOURCES_VALIDATION_REQUIRED":
        return {
            "action": "validate_resources",
            "message": "Validate the uploaded resources before generating the blueprint.",
        }
    return None


def _get_project(user_id: str, project_id: str) -> tuple[str, GraphState]:
    stored = get_repository().load(user_id, project_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return stored


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
    repository.save_with_event(
        user_id,
        project_id,
        thread_id,
        state,
        event_type,
        actor,
        _audit_payload(state, extra_audit),
    )
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
    return {
        "application": settings.app_name,
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


@app.get("/api/v1/health", tags=["platform"])
def api_health():
    """Versioned platform health endpoint for clients and CI smoke tests."""
    return {"status": "healthy", "api_version": "v1"}


@app.get("/api/v1/observability/summary", tags=["observability"])
def observability_summary():
    """Return process-local operational counters without source or prompt content."""
    return {"counters": observability_snapshot()}


@app.post("/auth/register")
def register(credentials: RegistrationRequest):
    try:
        profile = UserProfile(
            professional_role=credentials.professional_role,
            preferred_language=credentials.preferred_language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid professional profile or language.") from exc
    try:
        get_repository().register_user(credentials.user_id, credentials.password, profile)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    token = get_repository().create_auth_token(credentials.user_id)
    return {"user_id": credentials.user_id, "token": token, "profile": profile.model_dump()}


@app.post("/auth/login")
def login(credentials: CredentialsRequest):
    if not get_repository().authenticate_user(credentials.user_id, credentials.password):
        raise HTTPException(status_code=401, detail="Invalid user ID or password.")
    token = get_repository().create_auth_token(credentials.user_id)
    return {
        "user_id": credentials.user_id,
        "token": token,
        "profile": get_repository().get_user_profile(credentials.user_id).model_dump(),
    }


@app.post("/auth/reset-password")
def reset_password(credentials: CredentialsRequest):
    """Local-only, deliberately unsecured recovery flow requested for this app."""
    try:
        get_repository().reset_password_without_verification(credentials.user_id, credentials.password)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "user_id": credentials.user_id,
        "token": get_repository().create_auth_token(credentials.user_id),
        "profile": get_repository().get_user_profile(credentials.user_id).model_dump(),
    }


@app.get("/users/{user_id}/profile")
def get_user_profile(user_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    return {"profile": get_repository().get_user_profile(user_id).model_dump()}


@app.put("/users/{user_id}/profile")
def update_user_profile(
    user_id: str,
    request: UserProfileRequest,
    authenticated_user: str = Depends(_authenticated_user),
):
    _assert_owner(user_id, authenticated_user)
    try:
        profile = UserProfile(
            professional_role=request.professional_role,
            preferred_language=request.preferred_language,
        )
        get_repository().update_user_profile(user_id, profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid professional profile or language.") from exc
    return {"profile": profile.model_dump()}


@app.get("/app", include_in_schema=False)
def web_app():
    """Serve the local JavaScript interface."""
    return FileResponse(_web_dir / "index.html", media_type="text/html")


app.mount("/web", StaticFiles(directory=_web_dir), name="web")


@app.get("/users/{user_id}/projects")
def list_projects(user_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    return {"projects": get_repository().list_projects(user_id)}


@app.get("/users/{user_id}/templates")
def list_templates(user_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    return {"templates": get_repository().list_presentation_templates(user_id)}


@app.post("/users/{user_id}/templates")
async def upload_template(user_id: str, file: UploadFile = File(...), authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    if not (file.filename or "").lower().endswith(".pptx"):
        raise HTTPException(status_code=415, detail="Only .pptx templates are accepted.")
    content = await file.read()
    if not content or len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PowerPoint templates must be between 1 byte and 20 MB.")
    try:
        with ZipFile(io.BytesIO(content)) as archive:
            if "ppt/presentation.xml" not in archive.namelist():
                raise BadZipFile("Not a PowerPoint file")
    except BadZipFile as exc:
        raise HTTPException(status_code=422, detail="The uploaded file is not a valid .pptx template.") from exc
    return get_repository().save_presentation_template(user_id, file.filename or "template.pptx", content)


@app.post("/projects")
def create_or_open_project(request: ProjectRequest, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(request.user_id, authenticated_user)
    stored = get_repository().load(request.user_id, request.project_id)
    if stored is None:
        thread_id, state = get_repository().create_empty(request.user_id, request.project_id, request.project_name)
    else:
        thread_id, state = stored
    if stored is not None and request.project_name:
        get_repository().save_with_event(
            request.user_id,
            request.project_id,
            thread_id,
            state,
            "PROJECT_RENAMED",
            "user",
            _audit_payload(state, {"project_name": request.project_name}),
            request.project_name,
        )
    return _project_response(request.user_id, request.project_id, thread_id, state)


@app.get("/projects/{user_id}/{project_id}")
def get_project(user_id: str, project_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    thread_id, state = _get_project(user_id, project_id)
    return _project_response(user_id, project_id, thread_id, state)


@app.get("/projects/{user_id}/{project_id}/audit-events")
def list_audit_events(user_id: str, project_id: str, authenticated_user: str = Depends(_authenticated_user)):
    """Return immutable project events for traceability and operational review."""
    _assert_owner(user_id, authenticated_user)
    _get_project(user_id, project_id)
    return {"events": get_repository().list_events(user_id, project_id)}


@app.delete("/projects/{user_id}/{project_id}", status_code=204)
def delete_project(user_id: str, project_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    if not get_repository().delete_project(user_id, project_id):
        raise HTTPException(status_code=404, detail="Project not found.")


@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, authenticated_user: str = Depends(_authenticated_user)):
    _assert_owner(user_id, authenticated_user)
    get_repository().delete_user(user_id)


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
    ensure_history(state)
    state.messages.append(HumanMessage(content=request.message))
    add_turn(state, "user", request.message)
    state.user_profile = get_repository().get_user_profile(request.user_id)
    if state.presentation is not None:
        # Keep future blueprint/slide generations aligned with a profile update.
        state.presentation.owner_profile = state.user_profile
    try:
        result = get_agent().invoke(state, thread_id=thread_id)
    except Exception as exc:
        logger.exception("Language-model request failed for user=%s project=%s", request.user_id, request.project_id)
        error_message = str(exc)
        if "RESOURCE_EXHAUSTED" in error_message or "429" in error_message:
            raise HTTPException(
                status_code=429,
                detail="Gemini quota is exhausted. Retry later or use an API project with available quota.",
            ) from exc
        if isinstance(exc, httpx.ConnectError) or "nodename nor servname" in error_message:
            raise HTTPException(
                status_code=503,
                detail="Cannot reach Gemini. Check your Internet connection, DNS, or firewall, then retry.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail="The language-model provider could not process this request. Check the selected model and API key.",
        ) from exc
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
    """Extract a PDF and attach it as validated evidence to a presentation."""
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
        resource = ExtractPdfResourceUseCase().execute(filename, content)
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
        analysis = SummarizeResourcesUseCase().execute(state.resource_library, language=language)
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    except Exception as exc:
        logger.exception("Resource analysis failed for user=%s project=%s", user_id, project_id)
        raise HTTPException(status_code=502, detail="The model could not analyze the uploaded resources. Please retry.") from exc
    state.resource_analysis = analysis
    ensure_history(state)
    add_turn(state, "assistant", f"Resource overview:\n{analysis.summary}")
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
    try:
        ensure_resource_library(state)
        answer = DiscussResourcesUseCase().execute(
            state.resource_library, request.question, language=state.user_profile.preferred_language
        )
    except ValueError as exc:
        raise _workflow_conflict(exc) from exc
    except Exception as exc:
        logger.exception("Resource discussion failed for user=%s project=%s", user_id, project_id)
        raise HTTPException(status_code=502, detail="The model could not discuss the uploaded resources. Please retry.") from exc
    ensure_history(state)
    add_turn(state, "user", request.question)
    add_turn(state, "assistant", answer)
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


@app.post("/api/v1/conversations/jobs", tags=["conversations"], status_code=202)
def start_conversation_job(request: ChatRequest, authenticated_user: str = Depends(_authenticated_user)):
    """Run an agent turn asynchronously; poll the returned job for progress."""
    _assert_owner(request.user_id, authenticated_user)
    if get_repository().load(request.user_id, request.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    job = get_repository().create_job(request.user_id, request.project_id, "conversation")

    def work(progress):
        progress(25, "preparing_conversation")
        progress(55, "calling_model")
        result = chat(request, authenticated_user)
        progress(90, "persisting_project")
        return {"message": result.get("message", ""), "project_id": request.project_id}

    submit_job(get_repository(), request.user_id, str(job["job_id"]), "conversation", work)
    record_observability("async_job_queued", domain="conversation")
    return job


@app.post("/api/v1/resources/{user_id}/{project_id}/overview/jobs", tags=["resources"], status_code=202)
def start_resource_overview_job(
    user_id: str, project_id: str, authenticated_user: str = Depends(_authenticated_user)
):
    """Generate a resource overview asynchronously from the shared RAG layer."""
    _assert_owner(user_id, authenticated_user)
    if get_repository().load(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    job = get_repository().create_job(user_id, project_id, "resources")

    def work(progress):
        progress(30, "retrieving_pdf_passages")
        progress(65, "generating_overview")
        result = summarize_resources(user_id, project_id, authenticated_user)
        progress(90, "persisting_project")
        return {"project_id": project_id, "resource_analysis": result.get("resource_analysis")}

    submit_job(get_repository(), user_id, str(job["job_id"]), "resources", work)
    record_observability("async_job_queued", domain="resources")
    return job


@app.post("/api/v1/resources/{user_id}/{project_id}/discussion/jobs", tags=["resources"], status_code=202)
def start_resource_discussion_job(
    user_id: str,
    project_id: str,
    request: ResourceDiscussionRequest,
    authenticated_user: str = Depends(_authenticated_user),
):
    """Discuss project PDFs asynchronously without entering production mode."""
    _assert_owner(user_id, authenticated_user)
    if get_repository().load(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    job = get_repository().create_job(user_id, project_id, "resources")

    def work(progress):
        progress(30, "retrieving_pdf_passages")
        progress(65, "generating_discussion")
        result = discuss_resources(user_id, project_id, request, authenticated_user)
        progress(90, "persisting_project")
        return {"project_id": project_id, "messages": result.get("messages", [])[-1:]}

    submit_job(get_repository(), user_id, str(job["job_id"]), "resources", work)
    record_observability("async_job_queued", domain="resources")
    return job


@app.get("/api/v1/jobs/{user_id}/{job_id}", tags=["jobs"])
def get_async_job(user_id: str, job_id: str, authenticated_user: str = Depends(_authenticated_user)):
    """Poll a durable job record. Terminal states are completed and failed."""
    _assert_owner(user_id, authenticated_user)
    job = get_repository().get_job(user_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
