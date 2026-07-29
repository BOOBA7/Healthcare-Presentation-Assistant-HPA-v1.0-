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

    presenter_name: str | None = Field(default=None, description="Name shown on the title slide.")
    presenter_title: str | None = Field(default=None, description="Professional title shown on the title slide.")
    organization: str | None = Field(default=None, description="Affiliation shown on the title slide.")
    event_name: str | None = Field(default=None, description="Event name shown on the title slide.")
    venue: str | None = Field(default=None, description="Presentation venue shown on the title slide.")
    presentation_date: str | None = Field(default=None, description="Presentation date shown on the title slide.")
