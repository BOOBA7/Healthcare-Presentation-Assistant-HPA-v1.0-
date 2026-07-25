from app.application.validators.resource_validator import ResourceValidator
from app.domain.enums.workflow_step import WorkflowStep
from app.domain.models.presentation import Presentation


class ValidateResourcesUseCase:
    """
    Validates the scientific resources attached
    to a presentation.
    """

    def __init__(self) -> None:
        self.validator = ResourceValidator()

    def execute(self, presentation: Presentation) -> Presentation:
        """
        Validate the presentation resources.

        Args:
            presentation: Current presentation.

        Returns:
            Updated Presentation.
        """

        is_valid, messages = self.validator.validate(presentation.resources)

        if not is_valid:
            raise ValueError("\n".join(messages))

        presentation.state.resources_validated = True

        presentation.state.current_step = WorkflowStep.AUDIENCE_VALIDATION

        return presentation
