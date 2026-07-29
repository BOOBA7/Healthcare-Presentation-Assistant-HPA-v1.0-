from datetime import datetime

from app.ai.chains.blueprint_chain import BlueprintChain
from app.ai.mappers.blueprint_mapper import BlueprintMapper
from app.domain.enums.workflow_step import WorkflowStep
from app.domain.models.presentation import Presentation
from app.domain.models.agenda import Agenda
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.models.generation_record import GenerationRecord
from app.core.config import get_settings
from app.core.versioning import HARNESS_VERSION, PROMPT_VERSION, RETRIEVAL_VERSION, WORKFLOW_VERSION
from app.application.services.production_evidence_gate import ProductionEvidenceGate
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
            f"{presentation.context.topic} {presentation.context.objective}",
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
        presentation.generation_records.append(
            GenerationRecord(
                stage="blueprint",
                model_name=get_settings().gemini_model,
                prompt_version=PROMPT_VERSION,
                retrieval_version=RETRIEVAL_VERSION,
                harness_version=HARNESS_VERSION,
                workflow_version=WORKFLOW_VERSION,
            )
        )

        presentation.updated_at = datetime.now()

        return presentation
