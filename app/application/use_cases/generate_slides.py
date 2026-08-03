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
from app.domain.models.resource import Resource
from app.domain.models.resource_chunk import ResourceChunk
from app.domain.models.slide import Slide

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
        chunks: list[ResourceChunk] | None = None,
    ) -> Presentation:
        """
        Generate all presentation slides.
        """

        if presentation.blueprint is None:
            raise ValueError("Presentation blueprint has not been generated.")

        resolved_resources = resources if resources is not None else presentation.resources

        # Check every AI-owned outline before calling the model or replacing
        # the current slide collection. A single unsupported item must leave a
        # clear, recoverable human action rather than freezing the Project.
        for outline in presentation.blueprint.slides:
            if outline.content_origin == "user_authored":
                continue
            evidence_error = ProductionEvidenceGate.generation_error(
                presentation,
                f"{presentation.context.topic} {outline.title} {outline.objective} {outline.key_message}",
                resolved_resources,
                chunks,
            )
            if evidence_error:
                presentation.state.current_step = WorkflowStep.SLIDE_GENERATION
                presentation.state.workflow_status = WorkflowStatus.AWAITING_SLIDE_RESOLUTION
                presentation.state.blocked_slide_number = outline.slide_number
                presentation.state.slide_generation_error = evidence_error
                return presentation

        generated_slides: list[Slide] = []
        for outline in presentation.blueprint.slides:
            if outline.content_origin == "user_authored":
                # This is a deterministic transfer of user-provided content,
                # not an AI generation and therefore never calls the model.
                generated_slides.append(
                    Slide(
                        slide_number=outline.slide_number,
                        title=outline.title,
                        objective=outline.objective,
                        key_messages=[outline.key_message],
                        content=outline.key_message,
                        content_origin="user_authored",
                    )
                )
                continue
            schema = self.chain.invoke(
                presentation=presentation,
                outline=outline,
                resources=resolved_resources,
                chunks=chunks,
            )

            slide = self.mapper.to_domain(schema)
            self.evidence_validator.validate_slide(slide, resolved_resources)

            generated_slides.append(slide)

        # Commit the replacement only once every generated slide is ready.
        presentation.slides = generated_slides
        presentation.state.total_slides = len(presentation.slides)

        presentation.state.current_slide = presentation.state.total_slides

        presentation.state.current_step = WorkflowStep.SLIDE_VALIDATION
        presentation.state.workflow_status = WorkflowStatus.AWAITING_SLIDE_APPROVAL
        presentation.state.blocked_slide_number = None
        presentation.state.slide_generation_error = None
        presentation.generation_records.append(
            GenerationRecord(
                stage="slides",
                model_name=get_settings().gemini_model,
                prompt_version=PROMPT_VERSION,
                retrieval_version=RETRIEVAL_VERSION,
                retrieval_mode=presentation.evidence_context_mode.value,
                harness_version=HARNESS_VERSION,
                workflow_version=WORKFLOW_VERSION,
            )
        )

        presentation.updated_at = datetime.now(UTC)

        return presentation
