from dataclasses import dataclass, field


@dataclass
class ConversationContext:
    """
    Stores all information collected during
    the conversation before creating
    a Presentation.
    """

    title: str | None = None

    topic: str | None = None

    audience: str | None = None

    presentation_type: str | None = None

    language: str | None = None

    duration_minutes: int | None = None

    objective: str | None = None

    resources: list[str] = field(default_factory=list)

    def is_ready(self) -> bool:
        """
        Returns True when enough information
        has been collected to create
        the Presentation.
        """

        return all(
            [
                self.title,
                self.topic,
                self.audience,
                self.presentation_type,
                self.language,
                self.duration_minutes,
                self.objective,
            ]
        )
