from app.ai.chains.slide_chain import SlideChain
from app.ai.mappers.slide_mapper import SlideMapper
from app.application.validators.evidence_provenance_validator import EvidenceProvenanceValidator
from app.domain.enums.workflow_step import WorkflowStep
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.models.presentation import Presentation
from app.application.services.production_evidence_gate import ProductionEvidenceGate
from app.application.services.generation_metadata import append_generation_record
from app.ai.prompt_builders.evidence_context_builder import EvidenceContextBuilder
from app.domain.exceptions.validation_error import ValidationError
from app.domain.models.resource import Resource
from app.domain.models.resource_chunk import ResourceChunk
from app.domain.models.slide import Slide
from app.domain.models.slide_generation_blocker import SlideGenerationBlocker

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

        # Each outline is independent. A missing proof blocks that exact slide,
        # not every other supported slide in the Project.
        existing_by_number = {slide.slide_number: slide for slide in presentation.slides}
        generated_slides: list[Slide] = []
        blockers: list[SlideGenerationBlocker] = []
        invoked_model = False

        for outline in presentation.blueprint.slides:
            if outline.content_origin == "user_authored":
                existing = existing_by_number.get(outline.slide_number)
                if existing is not None and existing.content_origin == "user_authored":
                    generated_slides.append(existing)
                    continue
                # Deterministic transfer of human-authored blueprint content;
                # this branch must never initialise or call an LLM chain.
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

            existing = existing_by_number.get(outline.slide_number)
            if existing is not None:
                # A retry after another slide was resolved must not spend an
                # additional model call or overwrite approved work.
                generated_slides.append(existing)
                continue

            query = EvidenceContextBuilder.slide_query(presentation, outline)
            assessment = ProductionEvidenceGate.generation_assessment(
                presentation,
                query,
                resolved_resources,
                chunks,
            )
            if not assessment.is_sufficient:
                blockers.append(
                    SlideGenerationBlocker(
                        slide_number=outline.slide_number,
                        code="INSUFFICIENT_EVIDENCE",
                        message=(
                            "Validated PDF resources do not contain sufficient verifiable evidence "
                            "for this slide."
                        ),
                        diagnostic=assessment.diagnostic(),
                    )
                )
                continue

            try:
                schema = self.chain.invoke(
                    presentation=presentation,
                    outline=outline,
                    resources=resolved_resources,
                    chunks=chunks,
                )
                slide = self.mapper.to_domain(schema)
                self.evidence_validator.validate_slide(slide, resolved_resources)
            except ValidationError as exc:
                blockers.append(
                    SlideGenerationBlocker(
                        slide_number=outline.slide_number,
                        code="INVALID_AI_PROVENANCE",
                        message=str(exc),
                        diagnostic=assessment.diagnostic(),
                    )
                )
                continue

            invoked_model = True
            generated_slides.append(slide)

        presentation.slides = sorted(generated_slides, key=lambda slide: slide.slide_number)
        presentation.state.total_slides = len(presentation.blueprint.slides)
        presentation.state.current_slide = len(presentation.slides)
        presentation.state.slides_validated = False
        presentation.state.presentation_validated = False
        presentation.state.slide_generation_blockers = blockers

        if blockers:
            first_blocker = blockers[0]
            presentation.state.current_step = WorkflowStep.SLIDE_GENERATION
            presentation.state.workflow_status = WorkflowStatus.AWAITING_SLIDE_RESOLUTION
            presentation.state.blocked_slide_number = first_blocker.slide_number
            presentation.state.slide_generation_error = first_blocker.message
        else:
            presentation.state.current_step = WorkflowStep.SLIDE_VALIDATION
            presentation.state.workflow_status = WorkflowStatus.AWAITING_SLIDE_APPROVAL
            presentation.state.blocked_slide_number = None
            presentation.state.slide_generation_error = None

        if invoked_model:
            append_generation_record(presentation, "slides")

        return presentation
