from app.application.chat.chat_history import ChatHistory
from app.domain.models.presentation import Presentation


class ChatSession:
    """
    Represents one complete conversation
    between a user and the Healthcare
    Presentation Assistant.
    """

    def __init__(self) -> None:

        self.history = ChatHistory()

        self.presentation: Presentation | None = None

        self.is_completed: bool = False

    def attach_presentation(
        self,
        presentation: Presentation,
    ) -> None:
        """
        Attach a presentation to the current session.
        """

        self.presentation = presentation

    def has_presentation(self) -> bool:
        """
        Returns True if a presentation exists.
        """

        return self.presentation is not None

    def complete(self) -> None:
        """
        Mark the session as completed.
        """

        self.is_completed = True

    def reset(self) -> None:
        """
        Reset the current conversation.
        """

        self.history.clear()

        self.presentation = None

        self.is_completed = False
