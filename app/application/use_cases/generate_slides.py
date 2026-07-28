from app.ai.chains.slide_chain import SlideChain
from app.ai.mappers.slide_mapper import SlideMapper
from app.application.validators.evidence_provenance_validator import EvidenceProvenanceValidator
from app.domain.enums.workflow_step import WorkflowStep
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.models.generation_record import GenerationRecord
from app.core.config import get_settings
from app.core.versioning import HARNESS_VERSION, PROMPT_VERSION, RETRIEVAL_VERSION, WORKFLOW_VERSION
from app.domain.models.presentation import Presentation
from app.application.services.production_evidence_gate import ProductionEvidenceGate
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.resource import Resource

from datetime import UTC, datetime


class GenerateSlidesUseCase:
    """
    Generates all presentation slides
    from the validated blueprint.
    """

    def __init__(self) -> None:
        self.chain = SlideChain()
        self.mapper = SlideMapper()
        self.evidence_validator = EvidenceProvenanceValidator()

    def execute(
        self,
        presentation: Presentation,
        resources: list[Resource] | None = None,
    ) -> Presentation:
        """
        Generate all presentation slides.
        """

        if presentation.blueprint is None:
            raise ValueError("Presentation blueprint has not been generated.")

        presentation.slides = []

        for outline in presentation.blueprint.slides:
            evidence_error = ProductionEvidenceGate.generation_error(
                presentation,
                f"{presentation.context.topic} {outline.title} {outline.objective} {outline.key_message}",
                resources,
            )
            if evidence_error:
                raise WorkflowError("INSUFFICIENT_EVIDENCE", evidence_error)
            schema = self.chain.invoke(
                presentation=presentation,
                outline=outline,
                resources=resources,
            )

            slide = self.mapper.to_domain(schema)
            self.evidence_validator.validate_slide(slide, resources if resources is not None else presentation.resources)

            presentation.slides.append(slide)

        presentation.state.total_slides = len(presentation.slides)

        presentation.state.current_slide = presentation.state.total_slides

        presentation.state.current_step = WorkflowStep.SLIDE_VALIDATION
        presentation.state.workflow_status = WorkflowStatus.AWAITING_SLIDE_APPROVAL
        presentation.generation_records.append(
            GenerationRecord(
                stage="slides",
                model_name=get_settings().gemini_model,
                prompt_version=PROMPT_VERSION,
                retrieval_version=RETRIEVAL_VERSION,
                harness_version=HARNESS_VERSION,
                workflow_version=WORKFLOW_VERSION,
            )
        )

        presentation.updated_at = datetime.now(UTC)

        return presentation
