from uuid import uuid4

from app.ai.agents.healthcare_presentation_agent import (
    HealthcarePresentationAgent,
)
from app.domain.models.presentation import Presentation


class ChatSession:
    """
    Maintains a conversational session with
    the Healthcare Presentation Agent.
    """

    def __init__(self) -> None:
        self.agent = HealthcarePresentationAgent()
        self.thread_id = str(uuid4())

    def send(
        self,
        presentation: Presentation,
    ):
        """
        Send the current presentation to the agent.

        Returns the updated GraphState.
        """

        return self.agent.invoke(
            presentation=presentation,
            thread_id=self.thread_id,
        )
