from app.application.chat.conversation_context import (
    ConversationContext,
)
from app.application.chat.intent import Intent
from app.application.chat.intent_router import IntentRouter
from app.application.chat.chat_session import ChatSession


class ConversationManager:
    """
    Central orchestrator of the conversational workflow.

    It is responsible for:

    - routing user intents
    - maintaining conversation context
    - deciding the next question
    - determining when enough information
      has been collected to start the
      presentation workflow.
    """

    def __init__(self) -> None:

        self.router = IntentRouter()

    def process(
        self,
        session: ChatSession,
        message: str,
    ) -> str:
        """
        Process one user message and
        return the assistant response.
        """

        session.history.add_user_message(message)

        intent = self.router.route(message)

        response = self._handle_intent(
            session=session,
            intent=intent,
            message=message,
        )

        session.history.add_assistant_message(response)

        return response

    def _handle_intent(
        self,
        session: ChatSession,
        intent: Intent,
        message: str,
    ) -> str:

        if intent == Intent.GREETING:
            return "Hello! I can help you create a scientific healthcare presentation."

        if intent == Intent.HELP:
            return (
                "You can ask me to create a presentation, "
                "generate a blueprint, generate slides "
                "or export your presentation."
            )

        if intent == Intent.CREATE_PRESENTATION:
            if not hasattr(session, "conversation_context"):
                session.conversation_context = ConversationContext()

            return self._next_question(session.conversation_context)

        if intent == Intent.STATUS:
            if not hasattr(session, "conversation_context"):
                return "No presentation has been started."

            missing = session.conversation_context.missing_fields()

            if not missing:
                return "Presentation context is complete."

            return "Still missing: " + ", ".join(missing)

        return "I'm sorry, I didn't understand your request."

    def _next_question(
        self,
        context: ConversationContext,
    ) -> str:
        """
        Returns the next question required
        to complete the presentation context.
        """

        if context.topic is None:
            return "What is the presentation topic?"

        if context.audience is None:
            return "Who is the target audience?"

        if context.presentation_type is None:
            return "What type of presentation is it?"

        if context.language is None:
            return "Which language should I use?"

        if context.duration_minutes is None:
            return "How many minutes is the presentation?"

        if context.objective is None:
            return "What is the learning objective?"

        return "All required information has been collected."
