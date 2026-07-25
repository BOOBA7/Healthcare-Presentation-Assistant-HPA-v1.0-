from functools import lru_cache
import logging
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.ai.agents.healthcare_presentation_agent import HealthcarePresentationAgent
from app.ai.workflows.graph_state import GraphState
from app.application.use_cases.export_powerpoint import ExportPowerPointUseCase
from app.application.use_cases.extract_pdf_resource import ExtractPdfResourceUseCase
from app.core.config import get_settings
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.application.use_cases.workflow_steps import (
    RegenerateBlueprintUseCase,
    RegenerateSlideUseCase,
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


class ReviewRequest(BaseModel):
    comments: str = Field(default="", max_length=10_000)


def _project_response(user_id: str, project_id: str, thread_id: str, state: GraphState) -> dict:
    """Return only JSON-safe state needed by the browser interface."""
    presentation = state.presentation.model_dump(mode="json") if state.presentation else None
    messages = []
    for message in state.messages:
        if getattr(message, "type", "") not in {"human", "ai"}:
            continue
        content = getattr(message, "content", "")
        if not content:
            continue
        messages.append(
            {
                "role": "user" if isinstance(message, HumanMessage) else "assistant",
                "text": content,
            }
        )
    return {
        "user_id": user_id,
        "project_id": project_id,
        "thread_id": thread_id,
        "presentation": presentation,
        "messages": messages,
        "conversation_context": state.conversation_context.model_dump(mode="json"),
        "last_tool": state.last_tool,
        "error": state.error,
    }


def _get_project(user_id: str, project_id: str) -> tuple[str, GraphState]:
    stored = get_repository().load(user_id, project_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return stored


def _save_project(user_id: str, project_id: str, thread_id: str, state: GraphState) -> dict:
    get_repository().save(user_id, project_id, thread_id, state)
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


@app.get("/app", include_in_schema=False)
def web_app():
    """Serve the local JavaScript interface."""
    return FileResponse(_web_dir / "index.html", media_type="text/html")


app.mount("/web", StaticFiles(directory=_web_dir), name="web")


@app.get("/users/{user_id}/projects")
def list_projects(user_id: str):
    return {"project_ids": get_repository().list_project_ids(user_id)}


@app.post("/projects")
def create_or_open_project(request: ProjectRequest):
    stored = get_repository().load(request.user_id, request.project_id)
    thread_id, state = (
        stored
        if stored
        else get_repository().create_empty(request.user_id, request.project_id)
    )
    return _project_response(request.user_id, request.project_id, thread_id, state)


@app.get("/projects/{user_id}/{project_id}")
def get_project(user_id: str, project_id: str):
    thread_id, state = _get_project(user_id, project_id)
    return _project_response(user_id, project_id, thread_id, state)


@app.post("/chat")
def chat(request: ChatRequest):
    """Send a user message to the presentation workflow."""
    stored = get_repository().load(request.user_id, request.project_id)
    thread_id, state = (
        stored
        if stored
        else get_repository().create_empty(request.user_id, request.project_id)
    )
    state.messages.append(HumanMessage(content=request.message))
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
    get_repository().save(request.user_id, request.project_id, thread_id, saved_state)
    messages = result.get("messages", [])
    last_message = messages[-1] if messages else None

    return {
        "thread_id": thread_id,
        "project_id": request.project_id,
        "message": getattr(last_message, "content", ""),
        "last_tool": result.get("last_tool"),
        "error": result.get("error"),
        "presentation": saved_state.presentation.model_dump(mode="json") if saved_state.presentation else None,
        "project": _project_response(request.user_id, request.project_id, thread_id, saved_state),
    }


@app.post("/resources/pdf/{user_id}/{project_id}")
async def upload_pdf_resource(user_id: str, project_id: str, file: UploadFile = File(...)):
    """Extract a PDF and attach it as validated evidence to a presentation."""
    if file.content_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(status_code=415, detail="Only PDF uploads are accepted.")
    stored = get_repository().load(user_id, project_id)
    if stored is None or stored[1].presentation is None:
        raise HTTPException(status_code=409, detail="Create a presentation before uploading resources.")
    thread_id, state = stored
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF files are limited to 20 MB.")
    try:
        resource = ExtractPdfResourceUseCase().execute(Path(file.filename or "resource.pdf").name, content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    state.presentation.resources.append(resource)
    get_repository().save(user_id, project_id, thread_id, state)
    return {"resource_id": resource.id, "filename": resource.filename, "characters_extracted": len(resource.extracted_text or "")}


@app.post("/projects/{user_id}/{project_id}/resources/validate")
def approve_resources(user_id: str, project_id: str):
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = validate_resources.func(state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _save_project(user_id, project_id, thread_id, state)


@app.post("/projects/{user_id}/{project_id}/blueprint/items/{index}/approve")
def approve_blueprint_item(user_id: str, project_id: str, index: int, request: ReviewRequest):
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = ReviewBlueprintItemUseCase().execute(state, index, request.comments)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _save_project(user_id, project_id, thread_id, state)


@app.post("/projects/{user_id}/{project_id}/blueprint/items/{index}/reject")
def reject_blueprint_item(user_id: str, project_id: str, index: int, request: ReviewRequest):
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = RejectBlueprintItemUseCase().execute(state, index, request.comments)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _save_project(user_id, project_id, thread_id, state)


@app.post("/projects/{user_id}/{project_id}/blueprint/approve")
def approve_blueprint(user_id: str, project_id: str):
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = validate_blueprint.func(state, approved=True)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _save_project(user_id, project_id, thread_id, state)


@app.post("/projects/{user_id}/{project_id}/blueprint/regenerate")
def regenerate_blueprint(user_id: str, project_id: str):
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = RegenerateBlueprintUseCase().execute(state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _save_project(user_id, project_id, thread_id, state)


@app.post("/projects/{user_id}/{project_id}/slides/{index}/approve")
def approve_slide(user_id: str, project_id: str, index: int, request: ReviewRequest):
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = ReviewSlideUseCase().execute(state, index, request.comments)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _save_project(user_id, project_id, thread_id, state)


@app.post("/projects/{user_id}/{project_id}/slides/{index}/reject")
def reject_slide(user_id: str, project_id: str, index: int, request: ReviewRequest):
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = RejectSlideUseCase().execute(state, index, request.comments)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _save_project(user_id, project_id, thread_id, state)


@app.post("/projects/{user_id}/{project_id}/slides/{index}/regenerate")
def regenerate_slide(user_id: str, project_id: str, index: int):
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = RegenerateSlideUseCase().execute(state, index)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _save_project(user_id, project_id, thread_id, state)


@app.post("/projects/{user_id}/{project_id}/slides/approve")
def approve_slides(user_id: str, project_id: str):
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = validate_slides.func(state, approved=True)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _save_project(user_id, project_id, thread_id, state)


@app.post("/projects/{user_id}/{project_id}/presentation/approve")
def approve_final_presentation(user_id: str, project_id: str):
    thread_id, state = _get_project(user_id, project_id)
    try:
        state = validate_final_presentation.func(state, approved=True)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _save_project(user_id, project_id, thread_id, state)


@app.get("/presentations/{user_id}/{project_id}/export/pptx")
def export_powerpoint(user_id: str, project_id: str):
    """Download the generated presentation as a PowerPoint file."""
    stored = get_repository().load(user_id, project_id)
    if stored is None or stored[1].presentation is None:
        raise HTTPException(status_code=404, detail="Presentation not found.")
    _, state = stored
    try:
        path = ExportPowerPointUseCase().execute(state.presentation, _exports_dir)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", filename=f"{state.presentation.title}.pptx")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
