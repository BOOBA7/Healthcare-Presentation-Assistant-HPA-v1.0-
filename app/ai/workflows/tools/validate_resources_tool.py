from app.application.use_cases.validate_resources import ValidateResourcesUseCase
from app.ai.workflows.graph_state import GraphState


class ValidateResourcesTool:
    """
    Tool responsible for validating
    the uploaded scientific resources.
    """

    def __init__(self) -> None:
        self.use_case = ValidateResourcesUseCase()

    def __call__(self, state: GraphState) -> GraphState:
        """
        Execute the resource validation use case.
        """
        state.presentation = self.use_case.execute(state.presentation)
        return state
