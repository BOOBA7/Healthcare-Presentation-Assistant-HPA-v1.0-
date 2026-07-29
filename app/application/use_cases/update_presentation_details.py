"""Human-controlled title-slide metadata updates."""

from app.ai.workflows.graph_state import GraphState
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.exceptions.workflow_error import WorkflowError


class UpdatePresentationDetailsUseCase:
    """Update optional delivery details without asking the LLM to infer them."""

    _fields = {
        "presenter_name", "presenter_title", "organization", "event_name", "venue", "presentation_date"
    }

    def execute(self, state: GraphState, **values: str | None) -> GraphState:
        if state.presentation is None:
            raise WorkflowError("PRESENTATION_NOT_CREATED", "Create a presentation before editing its title-slide details.")
        updates = {
            field: value.strip() or None
            for field, value in values.items()
            if field in self._fields and isinstance(value, str)
        }
        context = state.presentation.context.model_copy(update=updates)
        state.presentation.context = context
        state.presentation.state.context = context

        # The title slide is part of the deliverable, so an already finalised
        # presentation needs one new human final approval after its metadata changes.
        if state.presentation.state.workflow_status in {
            WorkflowStatus.AWAITING_FINAL_APPROVAL,
            WorkflowStatus.READY_FOR_EXPORT,
            WorkflowStatus.EXPORTED,
        }:
            state.presentation.state.presentation_validated = False
            state.presentation.state.workflow_status = WorkflowStatus.AWAITING_FINAL_APPROVAL
        return state
