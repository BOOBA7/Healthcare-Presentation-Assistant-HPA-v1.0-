from app.ai.schemas.slide_schema import SlideSchema
from app.domain.models.slide import Slide


class SlideMapper:
    """
    Converts an AI SlideSchema into
    the domain Slide model.
    """

    def to_domain(
        self,
        schema: SlideSchema,
    ) -> Slide:

        return Slide(
            slide_number=schema.slide_number,
            title=schema.title,
            objective=schema.objective,
            key_messages=schema.key_messages,
            content=schema.content,
            speaker_notes=schema.speaker_notes,
            references=[reference.title for reference in schema.references],
            visual_recommendations=schema.visual_recommendations,
            is_validated=False,
        )
