"""Project, template and audit routes."""

from app.application.services.prototype_policy import PrototypePolicy

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.interfaces.api import main as api


router = APIRouter(tags=["projects"])


@router.get("/users/{user_id}/projects")
def list_projects(
    user_id: str, authenticated_user: str = Depends(api._authenticated_user)
) -> dict[str, object]:
    api._assert_owner(user_id, authenticated_user)
    return {"projects": api.get_repository().list_projects(user_id)}


@router.get("/users/{user_id}/dashboard")
def project_dashboard(
    user_id: str, authenticated_user: str = Depends(api._authenticated_user)
) -> dict[str, object]:
    """Return persisted Project cards for the authenticated owner."""
    api._assert_owner(user_id, authenticated_user)
    return api.get_repository().project_dashboard(user_id)


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
    prototype_declaration: str = Form(...),
    external_processing_acknowledged: bool = Form(...),
    authenticated_user: str = Depends(api._authenticated_user),
) -> dict[str, str]:
    api._assert_owner(user_id, authenticated_user)
    try:
        PrototypePolicy.declaration(prototype_declaration)
        if not external_processing_acknowledged:
            PrototypePolicy.declaration(None)
        PrototypePolicy.screen(file.filename)
    except ValueError as exc:
        raise api._workflow_conflict(exc) from exc
    if not (file.filename or "").lower().endswith(".pptx"):
        raise HTTPException(status_code=415, detail="Only .pptx templates are accepted.")
    content = await file.read()
    if not content or len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PowerPoint templates must be between 1 byte and 20 MB.")
    try:
        return api.get_repository().save_presentation_template(user_id, file.filename or "template.pptx", content, prototype_declaration=prototype_declaration)
    except ValueError as exc:
        raise api._workflow_conflict(exc) from exc


@router.post("/projects")
def create_or_open_project(
    request: api.ProjectRequest,
    authenticated_user: str = Depends(api._authenticated_user),
) -> dict[str, object]:
    api._assert_owner(request.user_id, authenticated_user)
    api._require_prototype_input(request)
    repository = api.get_repository()
    stored = repository.load(request.user_id, request.project_id)
    if request.prototype_declaration is not None:
        try:
            PrototypePolicy.declaration(request.prototype_declaration)
            if not request.external_processing_acknowledged:
                PrototypePolicy.declaration(None)
            if stored is not None:
                # Existing public publications may contain institutional contact
                # details. Declaration screens authored project content; source
                # contacts are reviewed independently at import/use time.
                PrototypePolicy.screen_state_content(stored[1], require_source_reviews=False)
        except ValueError as exc:
            raise api._workflow_conflict(exc) from exc
    if stored is None:
        try:
            thread_id, state = repository.create_empty(request.user_id, request.project_id, request.project_name)
        except ValueError as exc:
            raise api._workflow_conflict(exc) from exc
    else:
        thread_id, state = stored
    if request.prototype_declaration is not None:
        state.prototype_declaration = request.prototype_declaration
        if state.presentation is not None:
            state.presentation.prototype_declaration = state.prototype_declaration
        repository.save_with_event(
            request.user_id, request.project_id, thread_id, state,
            "PROTOTYPE_DECLARATION_RECORDED", "user",
            api._audit_payload(state, {"actor_user_id": authenticated_user, "external_processing_acknowledged": True}),
        )
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
    thread_id, state = api._get_project(user_id, project_id, require_prototype=False)
    return api._project_response(user_id, project_id, thread_id, state)


@router.get("/projects/{user_id}/{project_id}/audit-events")
def list_audit_events(
    user_id: str,
    project_id: str,
    authenticated_user: str = Depends(api._authenticated_user),
) -> dict[str, object]:
    api._assert_owner(user_id, authenticated_user)
    api._get_project(user_id, project_id, require_prototype=False)
    return {"events": api.get_repository().list_events(user_id, project_id)}


@router.delete("/projects/{user_id}/{project_id}", status_code=204)
def delete_project(
    user_id: str,
    project_id: str,
    authenticated_user: str = Depends(api._authenticated_user),
) -> None:
    api._assert_owner(user_id, authenticated_user)
    try:
        deleted = api.get_repository().delete_project(user_id, project_id)
    except ValueError as exc:
        raise api._workflow_conflict(exc) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found.")
    if api.get_repository().source_cleanup_pending():
        return api.JSONResponse({"deleted": True, "cleanup_pending": True}, status_code=202)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, authenticated_user: str = Depends(api._authenticated_user)) -> None:
    api._assert_owner(user_id, authenticated_user)
    try:
        api.get_repository().delete_user(user_id)
    except ValueError as exc:
        raise api._workflow_conflict(exc) from exc
    if api.get_repository().source_cleanup_pending():
        return api.JSONResponse({"deleted": True, "cleanup_pending": True}, status_code=202)
