"""Server-side evidence gate for production conversations and generation."""

from __future__ import annotations

import re

from app.ai.prompt_builders.evidence_context_builder import EvidenceContextBuilder
from app.ai.workflows.graph_state import GraphState
from app.application.services.resource_library import resolve_presentation_resources
from app.domain.enums.conversation_mode import ConversationMode
from app.application.services.observability import record


class ProductionEvidenceGate:
    """Block unsupported scientific content before it reaches the LLM."""

    _social_only = re.compile(
        r"^\s*(hi|hello|bonjour|salut|merci|thanks|thank you|ok|okay|salam|مرحبا|شكرا)[!.، ]*\s*$",
        re.IGNORECASE,
    )

    @classmethod
    def requires_evidence(cls, user_message: str) -> bool:
        """Return whether a chat turn needs user-PDF evidence before LLM use.

        This is deliberately an allow-list, not a medical-keyword detector.
        A factual question can be expressed with an unlimited number of terms,
        languages, abbreviations, or short follow-ups (for example, “What
        about CBT?”). Only a whole social acknowledgement may reach the LLM
        without retrieved PDF passages. Presentation setup and scope
        declarations are explicit human form actions, so free-text workflow
        chat cannot become an evidence-gate bypass.
        """
        return not cls.is_non_factual_coordination_turn(user_message)

    @classmethod
    def is_non_factual_coordination_turn(cls, user_message: str) -> bool:
        """Allow only a complete social acknowledgement without evidence."""
        return bool(cls._social_only.fullmatch(user_message))

    def block_reason(self, state: GraphState, user_message: str) -> str | None:
        """Return a safe user message, or ``None`` when the LLM may answer."""
        presentation = state.presentation
        mode = ConversationMode.PRODUCTION if presentation is not None else state.conversation_mode
        if not self.requires_evidence(user_message):
            return None

        # A presentation implies production for legacy persisted states created
        # before ``conversation_mode`` was introduced.
        if mode == ConversationMode.GENERAL:
            record("evidence_refusal", reason="general_mode_evidence_bound_request")
            return self._message(state, "general")

        if presentation is None:
            record("evidence_refusal", reason="production_without_presentation")
            return self._message(state, "missing")

        resources = resolve_presentation_resources(state)
        if not presentation.state.resources_validated:
            record("evidence_refusal", reason="resources_not_human_validated")
            return self._message(state, "missing")
        assessment = EvidenceContextBuilder().assess(
            presentation, user_message, resources, state.resource_chunks
        )
        if not assessment.has_validated_resources:
            record("evidence_refusal", reason="no_validated_resources")
            return self._message(state, "missing")

        if not assessment.is_sufficient:
            record("evidence_refusal", reason="insufficient_retrieved_evidence", score=assessment.best_score)
            return self._message(state, "insufficient")
        return None

    @staticmethod
    def generation_error(presentation, query: str, resources=None, chunks=None) -> str | None:
        assessment = ProductionEvidenceGate.generation_assessment(presentation, query, resources, chunks)
        if not assessment.has_validated_resources:
            record("generation_refusal", reason="no_validated_resources", **assessment.diagnostic())
            return "No user-validated PDF is available for this production step."
        if not assessment.is_sufficient:
            record(
                "generation_refusal",
                reason="insufficient_retrieved_evidence",
                score=assessment.best_score,
                **assessment.diagnostic(),
            )
            return "Validated PDF resources do not contain sufficient verifiable evidence for this production step."
        return None

    @staticmethod
    def generation_assessment(presentation, query: str, resources=None, chunks=None):
        """Return the auditable deterministic decision behind a generation gate."""
        return EvidenceContextBuilder().assess(presentation, query, resources, chunks)

    @staticmethod
    def _message(state: GraphState, reason: str) -> str:
        language = state.user_profile.preferred_language
        messages = {
            "fr": {
                "general": "Le chat ne traite pas de contenu scientifique sans PDF fourni par l’utilisateur. Pour créer une présentation, utilisez le formulaire Presentation Studio ; pour discuter des documents, ajoutez un PDF puis utilisez Resource Analysis.",
                "missing": "Je ne peux pas produire une réponse scientifique sans PDF validé. Ajoutez une ressource pertinente, puis validez-la.",
                "insufficient": "Les ressources validées ne contiennent pas de preuve suffisamment pertinente et vérifiable pour répondre. Ajoutez un PDF plus adapté ou précisez la question.",
            },
            "ar": {
                "general": "لا تعالج الدردشة محتوى علمياً من دون ملف PDF يقدمه المستخدم. لإنشاء عرض، استخدم نموذج Presentation Studio؛ ولمناقشة المستندات، أضف ملف PDF ثم استخدم Resource Analysis.",
                "missing": "لا يمكنني تقديم إجابة علمية من دون ملف PDF موثّق من المستخدم. أضف مورداً مناسباً ثم اعتمده.",
                "insufficient": "لا تحتوي الموارد المعتمدة على دليل كافٍ وقابل للتحقق للإجابة. أضف ملف PDF أكثر ملاءمة أو وضّح السؤال.",
            },
            "en": {
                "general": "Chat does not process scientific content without a user-provided PDF. Use the Presentation Studio form to create a presentation; add a PDF and use Resource Analysis to discuss documents.",
                "missing": "I cannot provide a scientific answer without a user-validated PDF. Add a relevant resource, then validate it.",
                "insufficient": "The validated resources do not contain sufficiently relevant, verifiable evidence to answer this question. Add a more suitable PDF or clarify the question.",
            },
        }
        return messages.get(language, messages["en"])[reason]
