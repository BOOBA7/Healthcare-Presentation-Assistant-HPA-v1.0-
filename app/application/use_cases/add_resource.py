"""Attach a new scientific resource and safely invalidate dependent artefacts."""

from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.models.presentation import Presentation
from app.domain.models.resource import Resource
from app.application.services.resource_library import resource_selection
from app.application.services.source_screening import SourceScreening
from app.application.services.source_date_policy import SourceDatePolicy


class AddResourceUseCase:
    """Add a verified resource at any workflow stage without leaving stale output."""

    def execute(self, presentation: Presentation, resource: Resource) -> Presentation:
        SourceScreening.resource(resource, require_text=True)
        SourceDatePolicy.require(resource)
        presentation.resources.append(resource_selection(resource))

        # A new source changes the evidence set. Existing generated content is
        # retained nowhere as "current" until the full source set is reviewed.
        presentation.agenda = None
        presentation.resource_analysis = None
        presentation.blueprint = None
        presentation.slides = []
        presentation.state.current_slide = 0
        presentation.state.total_slides = 0
        presentation.state.blocked_slide_number = None
        presentation.state.slide_generation_error = None
        presentation.state.slide_generation_blockers = []
        presentation.state.resources_validated = False
        presentation.state.blueprint_validated = False
        presentation.state.slides_validated = False
        presentation.state.presentation_validated = False
        presentation.state.workflow_status = WorkflowStatus.AWAITING_RESOURCE_VALIDATION
        return presentation
