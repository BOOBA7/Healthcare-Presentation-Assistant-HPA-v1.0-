"""Remove a project resource and invalidate every dependent generated artefact."""

from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.presentation import Presentation


class RemoveResourceUseCase:
    def execute(self, presentation: Presentation, resource_id: str) -> Presentation:
        original_count = len(presentation.resources)
        presentation.resources = [resource for resource in presentation.resources if resource.id != resource_id]
        if len(presentation.resources) == original_count:
            raise WorkflowError("RESOURCE_NOT_FOUND", "The selected resource does not belong to this project.")

        # A generated artefact may cite the deleted PDF. Reset downstream work
        # rather than leaving unsupported slides or approvals in the project.
        presentation.agenda = None
        presentation.resource_analysis = None
        presentation.blueprint = None
        presentation.slides = []
        presentation.state.current_slide = 0
        presentation.state.total_slides = 0
        presentation.state.blocked_slide_number = None
        presentation.state.slide_generation_error = None
        presentation.state.resources_validated = False
        presentation.state.blueprint_validated = False
        presentation.state.slides_validated = False
        presentation.state.presentation_validated = False
        presentation.state.workflow_status = (
            WorkflowStatus.AWAITING_RESOURCE_VALIDATION
            if presentation.resources
            else WorkflowStatus.AWAITING_RESOURCE_UPLOAD
        )
        return presentation
