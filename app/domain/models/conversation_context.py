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

    # None preserves legacy projects without inventing user input.
    target_slide_count: int | None = Field(default=None, strict=True, gt=0, le=200)
    special_instructions: str | None = Field(default=None, max_length=4000)
    professional_scope: str | None = Field(default=None, max_length=1000)
    is_multidisciplinary: bool | None = Field(default=None, strict=True)

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

        return not self.missing_fields()

    def missing_fields(self) -> list[str]:
        required_fields = (
            "topic", "audience", "presentation_type", "language", "duration_minutes", "objective",
            "target_slide_count", "special_instructions", "professional_scope", "is_multidisciplinary",
        )
        return [name for name in required_fields if getattr(self, name) is None
                or (name == "duration_minutes" and getattr(self, name) <= 0)
                or (isinstance(getattr(self, name), str) and not getattr(self, name).strip())]
