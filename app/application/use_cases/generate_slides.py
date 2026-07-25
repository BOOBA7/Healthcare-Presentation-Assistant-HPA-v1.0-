from app.ai.chains.slide_chain import SlideChain
from app.ai.mappers.slide_mapper import SlideMapper
from app.application.validators.evidence_provenance_validator import EvidenceProvenanceValidator
from app.domain.enums.workflow_step import WorkflowStep
from app.domain.models.presentation import Presentation

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
    ) -> Presentation:
        """
        Generate all presentation slides.
        """

        if presentation.blueprint is None:
            raise ValueError("Presentation blueprint has not been generated.")

        presentation.slides = []

        for outline in presentation.blueprint.slides:
            schema = self.chain.invoke(
                presentation=presentation,
                outline=outline,
            )

            slide = self.mapper.to_domain(schema)
            self.evidence_validator.validate_slide(slide, presentation.resources)

            presentation.slides.append(slide)

        presentation.state.total_slides = len(presentation.slides)

        presentation.state.current_slide = presentation.state.total_slides

        presentation.state.current_step = WorkflowStep.SLIDE_VALIDATION

        presentation.updated_at = datetime.now(UTC)

        return presentation
