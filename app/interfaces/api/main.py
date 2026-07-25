from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.ai.agents.healthcare_presentation_agent import HealthcarePresentationAgent
from app.ai.workflows.graph_state import GraphState
from app.application.use_cases.export_powerpoint import ExportPowerPointUseCase
from app.application.use_cases.extract_pdf_resource import ExtractPdfResourceUseCase
from app.core.config import get_settings
from app.interfaces.storage.user_session_repository import UserSessionRepository

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Healthcare Presentation Assistant API",
)
_exports_dir = Path("exports")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    user_id: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=128)


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
        error_message = str(exc)
        if "RESOURCE_EXHAUSTED" in error_message or "429" in error_message:
            raise HTTPException(
                status_code=429,
                detail="Gemini quota is exhausted. Retry later or use an API project with available quota.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail="The language-model provider could not process this request.",
        ) from exc
    get_repository().save(request.user_id, request.project_id, thread_id, GraphState(**result))
    messages = result.get("messages", [])
    last_message = messages[-1] if messages else None

    return {
        "thread_id": thread_id,
        "project_id": request.project_id,
        "message": getattr(last_message, "content", ""),
        "last_tool": result.get("last_tool"),
        "error": result.get("error"),
        "presentation": result.get("presentation"),
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
