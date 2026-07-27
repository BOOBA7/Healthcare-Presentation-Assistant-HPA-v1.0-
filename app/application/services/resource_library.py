"""Project-level resource-library helpers and legacy-state migration."""

from app.ai.workflows.graph_state import GraphState


def ensure_resource_library(state: GraphState) -> bool:
    """Expose old presentation resources in the project library once.

    Existing projects stored PDFs directly on a presentation.  Copying them
    preserves those projects while new uploads are independent from slide
    production.
    """
    if state.resource_library or state.presentation is None or not state.presentation.resources:
        return False
    state.resource_library = [resource.model_copy(deep=True) for resource in state.presentation.resources]
    return True
