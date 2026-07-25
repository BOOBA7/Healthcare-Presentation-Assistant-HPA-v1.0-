from app.application.use_cases.create_presentation import CreatePresentationUseCase
from app.ai.workflows.graph_state import GraphState
from app.domain.enums.workflow_step import WorkflowStep


class CreatePresentationTool:
    """
    Tool responsible for creating the Presentation
    domain object from a validated PresentationContext.
    """

    def __init__(self) -> None:
        self.use_case = CreatePresentationUseCase()

    def __call__(self, state: GraphState) -> GraphState:
        """
        Create the Presentation once the PresentationContext
        has been validated.
        """
        if state.presentation is not None:
            return state

        if state.presentation_context is None:
            raise ValueError("PresentationContext has not been validated.")

        state.presentation = self.use_case.execute(
            title=state.presentation_context.topic,
            context=state.presentation_context,
        )

        state.current_step = WorkflowStep.CREATE_PRESENTATION
        state.completed_steps.append(WorkflowStep.CREATE_PRESENTATION)

        return state
