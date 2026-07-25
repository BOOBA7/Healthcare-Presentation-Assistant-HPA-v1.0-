import logging

from app.ai.agents.agent_builder import AgentBuilder
from app.ai.workflows.graph_state import GraphState
from app.ai.workflows.presentation_graph import PresentationGraph
from app.ai.workflows.tools import (
    COGNITIVE_TOOLS,
)

logger = logging.getLogger(__name__)

class HealthcarePresentationAgent:
    """
    Cognitive engine of the Healthcare Presentation Assistant.
    """

    def __init__(self) -> None:
        logger.info("Initializing Healthcare Presentation Agent...")

        self.agent = AgentBuilder(tools=COGNITIVE_TOOLS).build()
        self.workflow = PresentationGraph(
            agent=self.agent,
            tools=COGNITIVE_TOOLS,
        ).compile()
        logger.info("Healthcare Presentation Agent initialized.")

    def invoke(self, state: GraphState, thread_id: str) -> dict:
        """
        Execute one reasoning session.
        """
        logger.info("Executing workflow (thread=%s)", thread_id)

        return self.workflow.invoke(
            state,
            config={
                "configurable": {
                    "thread_id": thread_id,
                }
            },
        )
