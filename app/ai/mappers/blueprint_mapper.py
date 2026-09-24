from app.ai.schemas.blueprint_schema import BlueprintSchema
from app.domain.models.blueprint import Blueprint
from app.domain.models.slide_outline import SlideOutline
from app.application.services.presentation_deidentification import PresentationDeidentification


class BlueprintMapper:
    """
    Converts an AI BlueprintSchema into
    the domain Blueprint model.
    """

    def to_domain(
        self,
        schema: BlueprintSchema,
    ) -> Blueprint:
        """
        Convert BlueprintSchema to Blueprint.
        """

        slides = [
            SlideOutline(
                slide_number=slide.slide_number,
                title=PresentationDeidentification.text(slide.title),
                objective=PresentationDeidentification.text(slide.objective),
                key_message=PresentationDeidentification.text(slide.key_message),
            )
            for slide in schema.slides
        ]

        return Blueprint(
            title=PresentationDeidentification.text(schema.title),
            learning_objective=PresentationDeidentification.text("\n".join(schema.learning_objectives)),
            target_number_of_slides=len(schema.slides),
            storytelling=PresentationDeidentification.text(schema.storytelling),
            slides=slides,
        )
