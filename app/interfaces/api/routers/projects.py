"""Project, template and audit routes."""

import io
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.interfaces.api import main as api


router = APIRouter(tags=["projects"])


@router.get("/users/{user_id}/projects")
def list_projects(
    user_id: str, authenticated_user: str = Depends(api._authenticated_user)
) -> dict[str, object]:
    api._assert_owner(user_id, authenticated_user)
    return {"projects": api.get_repository().list_projects(user_id)}


@router.get("/users/{user_id}/templates")
def list_templates(
    user_id: str, authenticated_user: str = Depends(api._authenticated_user)
) -> dict[str, object]:
    api._assert_owner(user_id, authenticated_user)
    return {"templates": api.get_repository().list_presentation_templates(user_id)}


@router.post("/users/{user_id}/templates")
async def upload_template(
    user_id: str,
    file: UploadFile = File(...),
    authenticated_user: str = Depends(api._authenticated_user),
) -> dict[str, str]:
    api._assert_owner(user_id, authenticated_user)
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
    return api.get_repository().save_presentation_template(user_id, file.filename or "template.pptx", content)


@router.post("/projects")
def create_or_open_project(
    request: api.ProjectRequest,
    authenticated_user: str = Depends(api._authenticated_user),
) -> dict[str, object]:
    api._assert_owner(request.user_id, authenticated_user)
    repository = api.get_repository()
    stored = repository.load(request.user_id, request.project_id)
    if stored is None:
        thread_id, state = repository.create_empty(request.user_id, request.project_id, request.project_name)
    else:
        thread_id, state = stored
    if stored is not None and request.project_name:
        repository.save_with_event(
            request.user_id,
            request.project_id,
            thread_id,
            state,
            "PROJECT_RENAMED",
            "user",
            api._audit_payload(state, {"project_name": request.project_name}),
            request.project_name,
        )
    return api._project_response(request.user_id, request.project_id, thread_id, state)


@router.get("/projects/{user_id}/{project_id}")
def get_project(
    user_id: str,
    project_id: str,
    authenticated_user: str = Depends(api._authenticated_user),
) -> dict[str, object]:
    api._assert_owner(user_id, authenticated_user)
    thread_id, state = api._get_project(user_id, project_id)
    return api._project_response(user_id, project_id, thread_id, state)


@router.get("/projects/{user_id}/{project_id}/audit-events")
def list_audit_events(
    user_id: str,
    project_id: str,
    authenticated_user: str = Depends(api._authenticated_user),
) -> dict[str, object]:
    api._assert_owner(user_id, authenticated_user)
    api._get_project(user_id, project_id)
    return {"events": api.get_repository().list_events(user_id, project_id)}


@router.delete("/projects/{user_id}/{project_id}", status_code=204)
def delete_project(
    user_id: str,
    project_id: str,
    authenticated_user: str = Depends(api._authenticated_user),
) -> None:
    api._assert_owner(user_id, authenticated_user)
    if not api.get_repository().delete_project(user_id, project_id):
        raise HTTPException(status_code=404, detail="Project not found.")


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, authenticated_user: str = Depends(api._authenticated_user)) -> None:
    api._assert_owner(user_id, authenticated_user)
    api.get_repository().delete_user(user_id)
