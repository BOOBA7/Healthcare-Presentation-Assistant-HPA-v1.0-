import logging
import re

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

        if self._needs_resource_validation_for_blueprint(state, latest_user_message):
            message = self._resource_validation_message(state.user_profile.preferred_language)
            action_state = state.model_copy(deep=True)
            action_state.messages.append(AIMessage(content=message))
            action_state.execution = ExecutionContext(
                tool_output={
                    "status": "action_required",
                    "action": "validate_resources",
                    "error_code": "RESOURCES_VALIDATION_REQUIRED",
                    "retryable": False,
                },
                error=message,
            )
            return action_state.model_dump()

        return self.workflow.invoke(
            state,
            config={
                "configurable": {
                    "thread_id": thread_id,
                }
            },
        )

    @staticmethod
    def _needs_resource_validation_for_blueprint(state: GraphState, message: str) -> bool:
        presentation = state.presentation
        if presentation is None or presentation.state.resources_validated or not presentation.resources:
            return False
        wants_generation = re.search(
            r"\b(generate|create|build|produce|g[ée]n[éeèe]rer|g[ée]n[éeèe]re|cr[ée]er|cr[ée]e|construire|construis|أنشئ|انشئ|ول[ّ]?د)\b",
            message,
            re.IGNORECASE,
        )
        wants_blueprint = re.search(
            r"\b(blueprint|outline|plan|structure|plan de pr[ée]sentation|مخطط|هيكل)\b",
            message,
            re.IGNORECASE,
        )
        return bool(wants_generation and wants_blueprint)

    @staticmethod
    def _resource_validation_message(language: str) -> str:
        messages = {
            "fr": "Avant de générer le blueprint, validez les ressources PDF importées. Utilisez le bouton « Valider les ressources et continuer », puis demandez-moi de générer le blueprint.",
            "ar": "قبل إنشاء المخطط، اعتمد ملفات PDF المرفوعة. استخدم زر «اعتماد المصادر والمتابعة» ثم اطلب مني إنشاء المخطط.",
            "en": "Before generating the blueprint, validate the uploaded PDF resources. Use the “Validate resources and continue” button, then ask me to generate the blueprint.",
        }
        return messages.get(language, messages["en"])
