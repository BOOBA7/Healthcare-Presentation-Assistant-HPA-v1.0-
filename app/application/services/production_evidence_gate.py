"""Server-side evidence gate for production conversations and generation."""

from __future__ import annotations

import re

from app.ai.prompt_builders.evidence_context_builder import EvidenceContextBuilder
from app.ai.workflows.graph_state import GraphState


class ProductionEvidenceGate:
    """Block unsupported scientific content before it reaches the LLM."""

    _social_only = re.compile(
        r"^\s*(hi|hello|bonjour|salut|merci|thanks|thank you|ok|okay|salam|مرحبا|شكرا)[!.، ]*\s*$",
        re.IGNORECASE,
    )
    _personal_context = re.compile(
        r"\b(i am|i'm|my role|my background|je suis|mon rôle|ma formation|"
        r"أنا|دوري|تكويني)\b",
        re.IGNORECASE,
    )
    _explicit_action = re.compile(
        r"\b(create|generate|continue|modify|regenerate|build|crée|cree|génère|genere|"
        r"continuer|modifier|régénère|regenerer|construis|أنشئ|انشئ|ول[ّ]?د|تابع)\b",
        re.IGNORECASE,
    )

    def block_reason(self, state: GraphState, user_message: str) -> str | None:
        """Return a safe user message, or ``None`` when the LLM may answer."""
        presentation = state.presentation
        if presentation is None or self._social_only.match(user_message) or self._personal_context.search(user_message):
            return None

        assessment = EvidenceContextBuilder().assess(presentation, user_message)
        if not assessment.has_validated_resources:
            return self._message(state, "missing")

        # Explicit workflow commands do not answer a scientific question; their
        # corresponding use case performs the same evidence check before LLM use.
        if self._explicit_action.search(user_message):
            return None
        if not assessment.is_sufficient:
            return self._message(state, "insufficient")
        return None

    @staticmethod
    def generation_error(presentation, query: str) -> str | None:
        assessment = EvidenceContextBuilder().assess(presentation, query)
        if not assessment.has_validated_resources:
            return "No user-validated PDF is available for this production step."
        if not assessment.is_sufficient:
            return "Validated PDF resources do not contain sufficient verifiable evidence for this production step."
        return None

    @staticmethod
    def _message(state: GraphState, reason: str) -> str:
        language = state.user_profile.preferred_language
        messages = {
            "fr": {
                "missing": "Je ne peux pas produire une réponse scientifique sans PDF validé. Ajoutez une ressource pertinente, puis validez-la.",
                "insufficient": "Les ressources validées ne contiennent pas de preuve suffisamment pertinente et vérifiable pour répondre. Ajoutez un PDF plus adapté ou précisez la question.",
            },
            "ar": {
                "missing": "لا يمكنني تقديم إجابة علمية من دون ملف PDF موثّق من المستخدم. أضف مورداً مناسباً ثم اعتمده.",
                "insufficient": "لا تحتوي الموارد المعتمدة على دليل كافٍ وقابل للتحقق للإجابة. أضف ملف PDF أكثر ملاءمة أو وضّح السؤال.",
            },
            "en": {
                "missing": "I cannot provide a scientific answer without a user-validated PDF. Add a relevant resource, then validate it.",
                "insufficient": "The validated resources do not contain sufficiently relevant, verifiable evidence to answer this question. Add a more suitable PDF or clarify the question.",
            },
        }
        return messages.get(language, messages["en"])[reason]
