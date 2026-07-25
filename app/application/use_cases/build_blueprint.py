from datetime import datetime

from app.ai.chains.blueprint_chain import BlueprintChain
from app.ai.mappers.blueprint_mapper import BlueprintMapper
from app.domain.enums.workflow_step import WorkflowStep
from app.domain.models.presentation import Presentation


class BuildBlueprintUseCase:
    """
    Generates the scientific blueprint of the presentation.
    """

    def __init__(self) -> None:

        self.chain = BlueprintChain()

        self.mapper = BlueprintMapper()

    def execute(
        self,
        presentation: Presentation,
    ) -> Presentation:
        """
        Generate the blueprint for a presentation.

        Parameters
        ----------
        presentation:
            Current presentation.

        Returns
        -------
        Presentation
        """

        blueprint_schema = self.chain.invoke(
            presentation,
        )

        presentation.blueprint = self.mapper.to_domain(
            blueprint_schema,
        )

        presentation.state.current_step = WorkflowStep.BLUEPRINT_VALIDATION

        presentation.updated_at = datetime.now()

        return presentation
