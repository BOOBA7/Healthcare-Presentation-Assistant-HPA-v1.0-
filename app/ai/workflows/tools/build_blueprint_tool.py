from app.application.use_cases.build_blueprint import BuildBlueprintUseCase
from app.ai.workflows.graph_state import GraphState


class BuildBlueprintTool:
    """
    Tool responsible for generating the presentation blueprint.
    """

    def __init__(self) -> None:
        self.use_case = BuildBlueprintUseCase()

    def __call__(self, state: GraphState) -> GraphState:
        """
        Execute the blueprint generation use case.
        """
        state.presentation = self.use_case.execute(state.presentation)
        return state
