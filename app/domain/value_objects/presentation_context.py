from pydantic import BaseModel, Field

from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType


class PresentationContext(BaseModel):
    """
    Contains all the information required
    to generate a healthcare presentation.
    """

    topic: str = Field(
        ...,
        description="Main topic of the presentation.",
    )

    audience: AudienceType = Field(
        ...,
        description="Target audience.",
    )

    presentation_type: PresentationType = Field(
        ...,
        description="Type of presentation.",
    )

    language: Language = Field(
        default=Language.ENGLISH,
        description="Presentation language.",
    )

    duration_minutes: int = Field(
        ...,
        gt=0,
        description="Presentation duration in minutes.",
    )

    objective: str = Field(
        ...,
        description="Main objective of the presentation.",
    )
