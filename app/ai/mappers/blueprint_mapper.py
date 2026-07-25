from app.ai.schemas.blueprint_schema import BlueprintSchema
from app.domain.models.blueprint import Blueprint
from app.domain.models.slide_outline import SlideOutline


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
                title=slide.title,
                objective=slide.objective,
                key_message=slide.key_message,
            )
            for slide in schema.slides
        ]

        return Blueprint(
            title=schema.title,
            learning_objective="\n".join(schema.learning_objectives),
            target_number_of_slides=len(schema.slides),
            storytelling=schema.storytelling,
            slides=slides,
        )
