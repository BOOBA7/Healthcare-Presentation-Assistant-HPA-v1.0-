"""Asynchronous conversation and resource-analysis routes."""

from fastapi import APIRouter, Depends, HTTPException

from app.application.services.observability import record as record_observability
from app.interfaces.api import main as api
from app.interfaces.api.job_runner import submit as submit_job


router = APIRouter(prefix="/api/v1", tags=["jobs"])


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
    job = repository.create_job(request.user_id, request.project_id, "conversation")

    def work(progress):
        progress(25, "preparing_conversation")
        progress(55, "calling_model")
        result = api.chat(request, authenticated_user)
        progress(90, "persisting_project")
        return {"message": result.get("message", ""), "project_id": request.project_id}

    submit_job(repository, request.user_id, str(job["job_id"]), "conversation", work)
    record_observability("async_job_queued", domain="conversation")
    return job


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
    job = repository.create_job(user_id, project_id, "resources")

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
    job = repository.create_job(user_id, project_id, "resources")

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
