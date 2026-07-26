from pydantic import BaseModel

from app.domain.enums.workflow_step import WorkflowStep
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.value_objects.audience_profile import AudienceProfile
from app.domain.value_objects.presentation_context import PresentationContext


class PresentationState(BaseModel):
    """
    Represents the current workflow state of a presentation.
    """

    context: PresentationContext

    audience_profile: AudienceProfile

    current_step: WorkflowStep = WorkflowStep.CONTEXT_VALIDATION

    workflow_status: WorkflowStatus = WorkflowStatus.CONTEXT_COLLECTION

    current_slide: int = 0

    total_slides: int = 0

    resources_validated: bool = False

    audience_validated: bool = False

    context_validated: bool = False

    blueprint_validated: bool = False

    slides_validated: bool = False

    presentation_validated: bool = False
