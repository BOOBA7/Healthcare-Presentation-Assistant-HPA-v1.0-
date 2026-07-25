from pydantic import BaseModel

from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType


class ConversationContext(BaseModel):
    """
    Stores all information progressively collected
    during the conversation before creating
    a PresentationContext.
    """

    topic: str | None = None

    audience: AudienceType | None = None

    presentation_type: PresentationType | None = None

    language: Language | None = None

    duration_minutes: int | None = None

    objective: str | None = None

    def is_complete(self) -> bool:
        """
        Returns True when enough information
        has been collected to create
        a PresentationContext.
        """

        return all(
            [
                self.topic,
                self.audience,
                self.presentation_type,
                self.language,
                self.duration_minutes,
                self.objective,
            ]
        )

    def missing_fields(self) -> list[str]:
        """
        Returns the list of missing fields.
        """

        missing = []

        if self.topic is None:
            missing.append("topic")

        if self.audience is None:
            missing.append("audience")

        if self.presentation_type is None:
            missing.append("presentation_type")

        if self.language is None:
            missing.append("language")

        if self.duration_minutes is None:
            missing.append("duration_minutes")

        if self.objective is None:
            missing.append("objective")

        return missing
