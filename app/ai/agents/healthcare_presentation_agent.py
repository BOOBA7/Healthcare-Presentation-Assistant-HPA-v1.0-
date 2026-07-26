import logging

from langchain_core.messages import AIMessage

from app.ai.agents.agent_builder import AgentBuilder
from app.ai.workflows.graph_state import GraphState
from app.ai.workflows.presentation_graph import PresentationGraph
from app.ai.workflows.tools import (
    COGNITIVE_TOOLS,
)
from app.application.services.production_evidence_gate import ProductionEvidenceGate
from app.domain.models.execution_context import ExecutionContext

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
        self.evidence_gate = ProductionEvidenceGate()
        logger.info("Healthcare Presentation Agent initialized.")

    def invoke(self, state: GraphState, thread_id: str) -> dict:
        """
        Execute one reasoning session.
        """
        logger.info("Executing workflow (thread=%s)", thread_id)

        latest_user_message = next(
            (
                str(message.content)
                for message in reversed(state.messages)
                if getattr(message, "type", "") == "human" and isinstance(message.content, str)
            ),
            "",
        )
        blocked_message = self.evidence_gate.block_reason(state, latest_user_message)
        if blocked_message:
            logger.info("production_evidence_gate_blocked thread=%s", thread_id)
            blocked_state = state.model_copy(deep=True)
            blocked_state.messages.append(AIMessage(content=blocked_message))
            blocked_state.execution = ExecutionContext(
                tool_output={
                    "status": "blocked",
                    "error_code": "INSUFFICIENT_EVIDENCE",
                    "retryable": False,
                },
                error=blocked_message,
            )
            return blocked_state.model_dump()

        return self.workflow.invoke(
            state,
            config={
                "configurable": {
                    "thread_id": thread_id,
                }
            },
        )
