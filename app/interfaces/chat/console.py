from app.interfaces.chat.chat_session import ChatSession
from app.application.use_cases.create_presentation import (
    CreatePresentationUseCase,
)
from app.domain.value_objects.presentation_context import (
    PresentationContext,
)


class Console:
    """
    Simple command-line interface for interacting
    with the Healthcare Presentation Assistant.
    """

    def __init__(self) -> None:
        self.session = ChatSession()

    def run(self) -> None:

        print("=" * 60)
        print("Healthcare Presentation Assistant")
        print("=" * 60)

        print()
        print("Conversation mode is not yet connected.")
        print("The workflow is ready.")
        print()

        while True:
            user_input = input("You > ").strip()

            if user_input.lower() in {
                "exit",
                "quit",
                "q",
            }:
                print("Goodbye.")
                break

            print()
            print("Assistant >")
            print("Conversation engine will be connected in the next step.")
            print()
