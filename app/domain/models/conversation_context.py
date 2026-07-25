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
        return [
            name for name, value in self.model_dump().items()
            if value is None
        ]
