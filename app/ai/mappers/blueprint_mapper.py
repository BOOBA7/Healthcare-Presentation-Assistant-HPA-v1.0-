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
        allowed_source_ids: set[str] | None = None,
    ) -> Blueprint:
        """
        Convert BlueprintSchema to Blueprint.
        """

        allowed = allowed_source_ids or set()
        unknown = {
            source_id
            for slide in schema.slides
            for source_id in slide.supporting_source_ids
            if source_id not in allowed
        }
        if unknown:
            raise ValueError(
                "Blueprint contains unknown supporting resource identifiers: "
                + ", ".join(sorted(unknown))
            )

        slides = [
            SlideOutline(
                slide_number=slide.slide_number,
                title=PresentationDeidentification.text(slide.title),
                objective=PresentationDeidentification.text(slide.objective),
                key_message=PresentationDeidentification.text(slide.key_message),
                supporting_source_ids=list(dict.fromkeys(slide.supporting_source_ids)),
                planned_visual=PresentationDeidentification.text(slide.planned_visual),
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
