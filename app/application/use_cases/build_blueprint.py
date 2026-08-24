from app.ai.chains.blueprint_chain import BlueprintChain
from app.ai.mappers.blueprint_mapper import BlueprintMapper
from app.domain.enums.workflow_step import WorkflowStep
from app.domain.models.presentation import Presentation
from app.domain.models.agenda import Agenda
from app.domain.enums.workflow_status import WorkflowStatus
from app.application.services.production_evidence_gate import ProductionEvidenceGate
from app.ai.prompt_builders.evidence_context_builder import EvidenceContextBuilder
from app.application.services.generation_metadata import append_generation_record
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.resource import Resource
from app.domain.models.resource_chunk import ResourceChunk


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
        resources: list[Resource] | None = None,
        chunks: list[ResourceChunk] | None = None,
        generation_stage: str = "blueprint",
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

        evidence_error = ProductionEvidenceGate.generation_error(
            presentation,
            EvidenceContextBuilder.presentation_query(presentation),
            resources,
            chunks,
        )
        if evidence_error:
            raise WorkflowError("INSUFFICIENT_EVIDENCE", evidence_error)

        blueprint_schema = self.chain.invoke(
            presentation,
            resources,
            chunks,
        )

        presentation.blueprint = self.mapper.to_domain(
            blueprint_schema,
        )
        # The LLM proposes the agenda through its ordered blueprint titles.
        # It is deliberately a separate, human-approved artefact.
        presentation.agenda = Agenda(
            items=[outline.title for outline in presentation.blueprint.slides]
        )

        presentation.state.current_step = WorkflowStep.BLUEPRINT_VALIDATION
        presentation.state.workflow_status = WorkflowStatus.AWAITING_AGENDA_APPROVAL
        append_generation_record(presentation, generation_stage)

        return presentation
