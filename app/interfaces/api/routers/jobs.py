"""Asynchronous conversation and resource-analysis routes."""

from fastapi import APIRouter, Depends, HTTPException

from app.application.services.observability import record as record_observability
from app.application.services.resource_library import resolve_presentation_resources
from app.application.services.workflow_policy import WorkflowPolicy
from app.application.use_cases.workflow_steps import (
    BuildBlueprintWorkflowUseCase,
    GenerateSlidesWorkflowUseCase,
)
from app.application.validators.presentation_compatibility_validator import (
    PresentationCompatibilityValidator,
)
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.exceptions.domain_error import DomainError
from app.domain.exceptions.project_job_running_error import ProjectJobRunningError
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.execution_context import ExecutionContext
from app.interfaces.api import main as api
from app.interfaces.api.job_runner import submit as submit_job


router = APIRouter(prefix="/api/v1", tags=["jobs"])


def _create_project_job(repository, user_id: str, project_id: str, domain: str) -> dict[str, object]:
    """Map the repository's Project-wide job lock to a stable API conflict."""
    try:
        return repository.create_job(user_id, project_id, domain)
    except ProjectJobRunningError as exc:
        raise api._workflow_conflict(exc) from exc


def _load_workflow_state(repository, user_id: str, project_id: str):
    """Reload authoritative state inside a worker; never trust a stale browser state."""
    stored = repository.load(user_id, project_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    thread_id, state = stored
    state.resource_chunks = repository.load_resource_chunks(user_id, project_id)
    return thread_id, state


def _require_generation_ready(state, *, action: str) -> None:
    """Run deterministic checks before any generation job is queued or executed."""
    presentation = state.presentation
    if presentation is None:
        raise WorkflowError("PRESENTATION_NOT_CREATED", "Create a presentation before generating content.")

    expected_status = (
        WorkflowStatus.BLUEPRINT_GENERATION if action == "blueprint" else WorkflowStatus.SLIDE_GENERATION
    )
    WorkflowPolicy.require_status(
        presentation.state.workflow_status,
        (expected_status,),
        f"generate the {action}",
    )
    if action == "blueprint" and not presentation.state.resources_validated:
        raise WorkflowError(
            "RESOURCES_NOT_VALIDATED",
            "Validate the selected PDF resources before generating the blueprint.",
        )
    if action == "slides" and not presentation.state.blueprint_validated:
        raise WorkflowError(
            "BLUEPRINT_NOT_VALIDATED",
            "Approve the agenda and every blueprint item before generating slides.",
        )

    clarification = PresentationCompatibilityValidator().clarification_message(
        presentation, resolve_presentation_resources(state)
    )
    if clarification:
        presentation.state.workflow_status = WorkflowStatus.AWAITING_SCOPE_CLARIFICATION
        raise WorkflowError("PRESENTATION_SCOPE_CLARIFICATION_REQUIRED", clarification)


def _persist_generation_failure(repository, user_id: str, project_id: str, thread_id: str, state, exc: Exception) -> None:
    """Keep failures actionable and durable instead of losing them in a job log."""
    if isinstance(exc, DomainError):
        code, message, retryable = exc.code, exc.user_message, exc.retryable
    else:
        code, message, retryable = "WORKFLOW_GENERATION_FAILED", "Generation could not be completed. Please retry.", True
    state.execution = ExecutionContext(
        last_tool=f"generate_{'blueprint' if state.presentation and state.presentation.blueprint is None else 'slides'}",
        tool_output={
            "status": "failed",
            "error_code": code,
            "retryable": retryable,
        },
        error=message,
    )
    api._save_project(
        user_id,
        project_id,
        thread_id,
        state,
        event_type="WORKFLOW_GENERATION_FAILED",
        actor="system",
        extra_audit={"error_code": code, "retryable": retryable},
    )


def _queue_generation_job(user_id: str, project_id: str, authenticated_user: str, *, action: str) -> dict[str, object]:
    """Queue one explicitly requested model generation behind server-owned guards."""
    api._assert_owner(user_id, authenticated_user)
    repository = api.get_repository()
    thread_id, state = _load_workflow_state(repository, user_id, project_id)
    try:
        _require_generation_ready(state, action=action)
    except WorkflowError as exc:
        # Scope clarification changes the durable workflow state and must be
        # visible even though no generation job was permitted.
        if state.presentation and state.presentation.state.workflow_status == WorkflowStatus.AWAITING_SCOPE_CLARIFICATION:
            api._save_project(
                user_id,
                project_id,
                thread_id,
                state,
                event_type="PRESENTATION_SCOPE_CLARIFICATION_REQUESTED",
                actor="system",
                extra_audit={"error_code": exc.code},
            )
        raise api._workflow_conflict(exc) from exc

    job = _create_project_job(repository, user_id, project_id, f"presentation_{action}")

    def work(progress):
        progress(25, f"validating_{action}_request")
        current_thread_id, current_state = _load_workflow_state(repository, user_id, project_id)
        try:
            _require_generation_ready(current_state, action=action)
            progress(55, f"generating_{action}")
            if action == "blueprint":
                current_state = BuildBlueprintWorkflowUseCase().execute(current_state)
                event_type = "BLUEPRINT_GENERATED_FROM_EXPLICIT_COMMAND"
            else:
                current_state = GenerateSlidesWorkflowUseCase().execute(current_state)
                event_type = "SLIDES_GENERATED_FROM_EXPLICIT_COMMAND"
            current_state.execution = ExecutionContext(last_tool=f"generate_{action}")
            progress(85, "persisting_project")
            saved = api._save_project(
                user_id,
                project_id,
                current_thread_id,
                current_state,
                event_type=event_type,
                actor="llm",
                extra_audit={"generation_command": action},
            )
            return {"project_id": project_id, "workflow": saved["workflow"]}
        except Exception as exc:
            _persist_generation_failure(repository, user_id, project_id, current_thread_id, current_state, exc)
            raise

    submit_job(repository, user_id, str(job["job_id"]), f"presentation_{action}", work)
    record_observability("async_job_queued", domain=f"presentation_{action}")
    return job


@router.post("/conversations/jobs", tags=["conversations"], status_code=202)
def start_conversation_job(
    request: api.ChatRequest,
    authenticated_user: str = Depends(api._authenticated_user),
) -> dict[str, object]:
    """Run an agent turn asynchronously; clients poll the returned job."""
    api._assert_owner(request.user_id, authenticated_user)
    repository = api.get_repository()
    if repository.load(request.user_id, request.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    job = _create_project_job(repository, request.user_id, request.project_id, "conversation")

    def work(progress):
        progress(25, "preparing_conversation")
        progress(55, "calling_model")
        result = api.chat(request, authenticated_user)
        progress(90, "persisting_project")
        return {"message": result.get("message", ""), "project_id": request.project_id}

    submit_job(repository, request.user_id, str(job["job_id"]), "conversation", work)
    record_observability("async_job_queued", domain="conversation")
    return job


@router.post("/projects/{user_id}/{project_id}/blueprint/jobs", tags=["presentation"], status_code=202)
def start_blueprint_generation_job(
    user_id: str,
    project_id: str,
    authenticated_user: str = Depends(api._authenticated_user),
) -> dict[str, object]:
    """Generate a blueprint only after an explicit UI command and server checks."""
    return _queue_generation_job(user_id, project_id, authenticated_user, action="blueprint")


@router.post("/projects/{user_id}/{project_id}/slides/jobs", tags=["presentation"], status_code=202)
def start_slide_generation_job(
    user_id: str,
    project_id: str,
    authenticated_user: str = Depends(api._authenticated_user),
) -> dict[str, object]:
    """Generate slides only after an explicit UI command and server checks."""
    return _queue_generation_job(user_id, project_id, authenticated_user, action="slides")


@router.post("/resources/{user_id}/{project_id}/overview/jobs", tags=["resources"], status_code=202)
def start_resource_overview_job(
    user_id: str,
    project_id: str,
    authenticated_user: str = Depends(api._authenticated_user),
) -> dict[str, object]:
    """Generate a resource overview asynchronously from the local RAG layer."""
    api._assert_owner(user_id, authenticated_user)
    repository = api.get_repository()
    if repository.load(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    job = _create_project_job(repository, user_id, project_id, "resources")

    def work(progress):
        progress(30, "retrieving_pdf_passages")
        progress(65, "generating_overview")
        result = api.summarize_resources(user_id, project_id, authenticated_user)
        progress(90, "persisting_project")
        return {"project_id": project_id, "resource_analysis": result.get("resource_analysis")}

    submit_job(repository, user_id, str(job["job_id"]), "resources", work)
    record_observability("async_job_queued", domain="resources")
    return job


@router.post("/resources/{user_id}/{project_id}/discussion/jobs", tags=["resources"], status_code=202)
def start_resource_discussion_job(
    user_id: str,
    project_id: str,
    request: api.ResourceDiscussionRequest,
    authenticated_user: str = Depends(api._authenticated_user),
) -> dict[str, object]:
    """Discuss project PDFs asynchronously without entering production mode."""
    api._assert_owner(user_id, authenticated_user)
    repository = api.get_repository()
    if repository.load(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    job = _create_project_job(repository, user_id, project_id, "resources")

    def work(progress):
        progress(30, "retrieving_pdf_passages")
        progress(65, "generating_discussion")
        result = api.discuss_resources(user_id, project_id, request, authenticated_user)
        progress(90, "persisting_project")
        return {"project_id": project_id, "resource_messages": result.get("resource_messages", [])[-1:]}

    submit_job(repository, user_id, str(job["job_id"]), "resources", work)
    record_observability("async_job_queued", domain="resources")
    return job


@router.get("/jobs/{user_id}/{job_id}")
def get_async_job(
    user_id: str,
    job_id: str,
    authenticated_user: str = Depends(api._authenticated_user),
) -> dict[str, object]:
    """Poll a durable job record; terminal statuses are completed and failed."""
    api._assert_owner(user_id, authenticated_user)
    job = api.get_repository().get_job(user_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job
