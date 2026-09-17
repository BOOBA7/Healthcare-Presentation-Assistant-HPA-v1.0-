"""Conservative dependency invalidation when a source leaves a Project."""

from app.domain.enums.presentation_status import PresentationStatus
from app.domain.enums.workflow_step import WorkflowStep
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.models.execution_context import ExecutionContext


def invalidate_source_dependents(state):
    # Transcripts and generated material may quote any previously available PDF.
    state.messages = []
    state.conversation_history = []
    state.resource_conversation_history = []
    state.conversation_memory_summary = ""
    state.resource_analysis = None
    state.planning_transfer = None
    state.resource_chunks = []
    state.execution = ExecutionContext()
    presentation = state.presentation
    if presentation is None:
        return
    presentation.agenda = None
    presentation.evidence_coverage = None
    presentation.blueprint = None
    presentation.slides = []
    presentation.resource_analysis = None
    presentation.generation_records = []
    presentation.status = PresentationStatus.IN_PROGRESS
    progress = presentation.state
    progress.current_step = WorkflowStep.RESOURCE_VALIDATION
    progress.current_slide = progress.total_slides = 0
    progress.blocked_slide_number = None
    progress.slide_generation_error = None
    progress.slide_generation_blockers = []
    progress.resources_validated = progress.blueprint_validated = False
    progress.slides_validated = progress.presentation_validated = False
    progress.workflow_status = (WorkflowStatus.AWAITING_RESOURCE_VALIDATION
                                if presentation.resources else WorkflowStatus.AWAITING_RESOURCE_UPLOAD)
