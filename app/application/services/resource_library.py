"""Project-level resource-library helpers and legacy-state migration."""

from app.ai.workflows.graph_state import GraphState
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.resource import Resource


def resource_selection(resource: Resource) -> Resource:
    """Return lightweight presentation metadata for a library resource.

    Extracted text and page payloads stay exclusively in ``resource_library``.
    A presentation stores only an explicit selection by resource identifier.
    """
    return Resource(
        id=resource.id,
        filename=resource.filename,
        title=resource.title,
        source=resource.source,
        language=resource.language,
        file_type=resource.file_type,
        path=resource.path,
        is_validated=resource.is_validated,
        uploaded_at=resource.uploaded_at,
    )


def resolve_presentation_resources(state: GraphState) -> list[Resource]:
    """Resolve the selected resource identifiers to their single stored source."""
    if state.presentation is None:
        return []
    library_by_id = {resource.id: resource for resource in state.resource_library}
    resolved: list[Resource] = []
    missing: list[str] = []
    for selection in state.presentation.resources:
        source = library_by_id.get(selection.id)
        if source is None:
            # Compatibility for transient legacy states before they are saved.
            if selection.extracted_pages or selection.extracted_text:
                source = selection
            else:
                missing.append(selection.id)
                continue
        resolved.append(source)
    if missing:
        raise WorkflowError(
            "SELECTED_RESOURCE_MISSING",
            "A selected presentation resource is missing from the Project library.",
        )
    return resolved


def ensure_resource_library(state: GraphState) -> bool:
    """Migrate old full presentation resources and normalize selections.

    Existing projects stored PDFs directly on a presentation.  Copying them
    preserves those projects while new uploads are independent from slide
    production.
    """
    presentation = state.presentation
    if presentation is None:
        return False

    changed = False
    library_ids = {resource.id for resource in state.resource_library}
    for selected in presentation.resources:
        if selected.id not in library_ids and (selected.extracted_text or selected.extracted_pages):
            state.resource_library.append(selected.model_copy(deep=True))
            library_ids.add(selected.id)
            changed = True

    normalized = [resource_selection(selected) for selected in presentation.resources]
    if any(selected.extracted_text or selected.extracted_pages for selected in presentation.resources):
        presentation.resources = normalized
        changed = True
    return changed
