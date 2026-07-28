from app.application.validators.resource_validator import ResourceValidator
from app.domain.enums.workflow_step import WorkflowStep
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.models.presentation import Presentation
from app.domain.models.resource import Resource
from app.application.services.workflow_policy import WorkflowPolicy


class ValidateResourcesUseCase:
    """
    Validates the scientific resources attached
    to a presentation.
    """

    def __init__(self) -> None:
        self.validator = ResourceValidator()

    def execute(self, presentation: Presentation, resources: list[Resource] | None = None) -> Presentation:
        """
        Validate the presentation resources.

        Args:
            presentation: Current presentation.

        Returns:
            Updated Presentation.
        """

        WorkflowPolicy.require_status(
            presentation.state.workflow_status,
            (WorkflowStatus.AWAITING_RESOURCE_UPLOAD, WorkflowStatus.AWAITING_RESOURCE_VALIDATION),
            "validate resources",
        )
        # A presentation contains lightweight selections.  The project library
        # owns the parsed PDF payload used for validation and retrieval.
        is_valid, messages = self.validator.validate(resources if resources is not None else presentation.resources)

        if not is_valid:
            raise ValueError("\n".join(messages))

        presentation.state.resources_validated = True

        presentation.state.current_step = WorkflowStep.AUDIENCE_VALIDATION
        presentation.state.workflow_status = WorkflowStatus.BLUEPRINT_GENERATION

        return presentation
