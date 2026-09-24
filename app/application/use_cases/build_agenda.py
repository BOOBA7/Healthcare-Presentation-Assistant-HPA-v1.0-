from app.ai.chains.agenda_chain import AgendaChain
from app.application.services.evidence_coverage import EvidenceCoverageService
from app.application.services.generation_metadata import append_generation_record
from app.application.services.production_evidence_gate import ProductionEvidenceGate
from app.ai.prompt_builders.evidence_context_builder import EvidenceContextBuilder
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.agenda import Agenda
from app.domain.models.presentation import Presentation
from app.domain.models.resource import Resource
from app.domain.models.resource_chunk import ResourceChunk
from app.domain.enums.workflow_status import WorkflowStatus


class BuildAgendaUseCase:
    """Generate editable high-level sections without creating a Blueprint."""

    def __init__(self, chain: AgendaChain | None = None) -> None:
        self.chain = chain

    def execute(
        self,
        presentation: Presentation,
        resources: list[Resource] | None = None,
        chunks: list[ResourceChunk] | None = None,
    ) -> Presentation:
        resolved = resources or presentation.resources
        EvidenceCoverageService().require_current(presentation, resolved, chunks or [])
        evidence_error = ProductionEvidenceGate.generation_error(
            presentation, EvidenceContextBuilder.presentation_query(presentation), resources, chunks
        )
        if evidence_error:
            raise WorkflowError("INSUFFICIENT_EVIDENCE", evidence_error)
        schema = (self.chain or AgendaChain()).invoke(presentation, resources, chunks)
        sections = [section.strip() for section in schema.sections if section.strip()]
        if not sections:
            raise WorkflowError("AGENDA_EMPTY", "Agenda generation returned no reviewable section.")
        presentation.agenda = Agenda(items=sections)
        presentation.blueprint = None
        presentation.state.blueprint_validated = False
        presentation.state.workflow_status = WorkflowStatus.AWAITING_AGENDA_APPROVAL
        append_generation_record(presentation, "agenda")
        return presentation
