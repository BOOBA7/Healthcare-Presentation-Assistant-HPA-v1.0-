from typing import List

from app.application.chat.message import ChatMessage, Role


class ChatHistory:
    """
    Stores the complete conversation exchanged
    between the user and the assistant.
    """

    def __init__(self) -> None:
        self._messages: List[ChatMessage] = []

    def add(
        self,
        message: ChatMessage,
    ) -> None:
        """
        Add a new message to the conversation.
        """

        self._messages.append(message)

    def add_user_message(
        self,
        content: str,
    ) -> None:
        """
        Add a user message.
        """

        self.add(
            ChatMessage(
                role=Role.USER,
                content=content,
            )
        )

    def add_assistant_message(
        self,
        content: str,
    ) -> None:
        """
        Add an assistant message.
        """

        self.add(
            ChatMessage(
                role=Role.ASSISTANT,
                content=content,
            )
        )

    def extend(
        self,
        messages: List[ChatMessage],
    ) -> None:
        """
        Add multiple messages.
        """

        self._messages.extend(messages)

    def clear(self) -> None:
        """
        Remove all messages.
        """

        self._messages.clear()

    def last(self) -> ChatMessage | None:
        """
        Return the latest message.
        """

        if not self._messages:
            return None

        return self._messages[-1]

    def all(self) -> List[ChatMessage]:
        """
        Return the complete conversation.
        """

        return list(self._messages)

    def size(self) -> int:
        """
        Return the number of messages.
        """

        return len(self._messages)

    def is_empty(self) -> bool:
        """
        Returns True if the history is empty.
        """

        return len(self._messages) == 0
