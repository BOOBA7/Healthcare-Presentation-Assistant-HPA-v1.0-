from app.application.chat.chat_session import ChatSession
from app.application.chat.conversation_manager import (
    ConversationManager,
)


class ChatCLI:
    """
    Simple command-line interface for interacting
    with the Healthcare Presentation Assistant.
    """

    def __init__(self) -> None:
        self.manager = ConversationManager()

        self.session = ChatSession()

    def run(self) -> None:
        """
        Start the interactive chat session.
        """

        print("=" * 60)
        print("Healthcare Presentation Assistant")
        print("=" * 60)
        print()
        print("Type 'exit' to quit.")
        print()

        while True:
            user_message = input("You > ").strip()

            if not user_message:
                continue

            if user_message.lower() in [
                "exit",
                "quit",
            ]:
                print()
                print("Goodbye.")
                break

            response = self.manager.process(
                session=self.session,
                message=user_message,
            )

            print()
            print(f"HPA > {response}")
            print()
