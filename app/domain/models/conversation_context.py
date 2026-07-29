from pydantic import BaseModel, Field

from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType


class ConversationContext(BaseModel):
    """
    Temporary conversational context progressively built
    during the interaction with the user.

    Unlike PresentationContext, every field is optional.
    The object becomes complete before being converted into
    a PresentationContext.
    """

    topic: str | None = Field(
        default=None,
        description="Presentation topic.",
    )

    audience: AudienceType | None = Field(
        default=None,
        description="Target audience.",
    )

    presentation_type: PresentationType | None = Field(
        default=None,
        description="Presentation type.",
    )

    language: Language | None = Field(
        default=None,
        description="Presentation language.",
    )

    duration_minutes: int | None = Field(
        default=None,
        description="Presentation duration.",
    )

    objective: str | None = Field(
        default=None,
        description="Presentation objective.",
    )

    presenter_name: str | None = None
    presenter_title: str | None = None
    organization: str | None = None
    event_name: str | None = None
    venue: str | None = None
    presentation_date: str | None = None

    def is_complete(self) -> bool:
        """
        Returns True when every mandatory field
        has been collected.
        """

        return all(
            (
                self.topic,
                self.audience,
                self.presentation_type,
                self.language,
                self.duration_minutes,
                self.objective,
            )
        )

    def missing_fields(self) -> list[str]:
        required_fields = (
            "topic", "audience", "presentation_type", "language", "duration_minutes", "objective"
        )
        return [name for name in required_fields if getattr(self, name) is None]
