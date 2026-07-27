"""Use cases for the project resource library and production selection."""

from app.ai.workflows.graph_state import GraphState
from app.application.use_cases.add_resource import AddResourceUseCase
from app.application.use_cases.remove_resource import RemoveResourceUseCase
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.resource import Resource


class AddProjectResourceUseCase:
    def execute(self, state: GraphState, resource: Resource) -> GraphState:
        if any(item.id == resource.id for item in state.resource_library):
            raise WorkflowError("RESOURCE_ALREADY_EXISTS", "This PDF is already in the Project library.")
        state.resource_library.append(resource)
        state.resource_analysis = None
        return state


class AttachResourceToPresentationUseCase:
    def execute(self, state: GraphState, resource_id: str) -> GraphState:
        if state.presentation is None:
            raise WorkflowError("PRESENTATION_NOT_FOUND", "Create a presentation before selecting production resources.")
        resource = next((item for item in state.resource_library if item.id == resource_id), None)
        if resource is None:
            raise WorkflowError("RESOURCE_NOT_FOUND", "The selected PDF is not in this Project library.")
        if any(item.id == resource_id for item in state.presentation.resources):
            return state
        AddResourceUseCase().execute(state.presentation, resource.model_copy(deep=True))
        return state


class DetachResourceFromPresentationUseCase:
    def execute(self, state: GraphState, resource_id: str) -> GraphState:
        if state.presentation is None:
            raise WorkflowError("PRESENTATION_NOT_FOUND", "Presentation not found.")
        RemoveResourceUseCase().execute(state.presentation, resource_id)
        return state


class RemoveProjectResourceUseCase:
    def execute(self, state: GraphState, resource_id: str) -> GraphState:
        if not any(item.id == resource_id for item in state.resource_library):
            raise WorkflowError("RESOURCE_NOT_FOUND", "The selected PDF is not in this Project library.")
        if state.presentation and any(item.id == resource_id for item in state.presentation.resources):
            RemoveResourceUseCase().execute(state.presentation, resource_id)
        state.resource_library = [item for item in state.resource_library if item.id != resource_id]
        state.resource_analysis = None
        return state
