from app.application.use_cases.generate_slides import GenerateSlidesUseCase
from app.ai.workflows.graph_state import GraphState


class GenerateSlidesTool:
    """
    Tool responsible for generating
    all presentation slides.
    """

    def __init__(self) -> None:
        self.use_case = GenerateSlidesUseCase()

    def __call__(self, state: GraphState) -> GraphState:
        """
        Generate all slides for the presentation.
        """
        state.presentation = self.use_case.execute(state.presentation)
        return state
