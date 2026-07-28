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
    _scientific_request = re.compile(
        r"\b(what is|what are|what does|what do|explain|treatment|therapy|diagnos|dose|dosing|drug|medication|"
        r"guideline|recommend\w*|indication|contraindication|adverse|disease|depression|clinical|"
        r"qu.est.ce|explique|traitement|th.rapie|diagnostic|dose|posologie|m.dicament|recommand\w*|"
        r"indication|contre.indication|effet ind.sirable|maladie|d.pression|clinique|"
        r"ما هو|ما هي|اشرح|علاج|تشخيص|جرعة|دواء|توصي|مرض|اكتئاب|سريري)\b",
        re.IGNORECASE,
    )

    def block_reason(self, state: GraphState, user_message: str) -> str | None:
        """Return a safe user message, or ``None`` when the LLM may answer."""
        presentation = state.presentation
        if self._social_only.match(user_message) or self._personal_context.search(user_message):
            return None

        # A presentation implies production for legacy persisted states created
        # before ``conversation_mode`` was introduced.
        mode = ConversationMode.PRODUCTION if presentation is not None else state.conversation_mode
        if mode == ConversationMode.GENERAL:
            if self._scientific_request.search(user_message):
                record("evidence_refusal", reason="general_mode_scientific_request")
                return self._message(state, "general")
            return None

        if presentation is None:
            record("evidence_refusal", reason="production_without_presentation")
            return self._message(state, "missing")

        # The production conversation becomes evidence-bound only for a
        # scientific/factual request. Planning and navigation remain natural.
        if not self._scientific_request.search(user_message):
            return None

        resources = resolve_presentation_resources(state)
        if not presentation.state.resources_validated:
            record("evidence_refusal", reason="resources_not_human_validated")
            return self._message(state, "missing")
        assessment = EvidenceContextBuilder().assess(presentation, user_message, resources)
        if not assessment.has_validated_resources:
            record("evidence_refusal", reason="no_validated_resources")
            return self._message(state, "missing")

        # Explicit workflow commands do not answer a scientific question; their
        # corresponding use case performs the same evidence check before LLM use.
        if self._explicit_action.search(user_message):
            return None
        if not assessment.is_sufficient:
            record("evidence_refusal", reason="insufficient_retrieved_evidence", score=assessment.best_score)
            return self._message(state, "insufficient")
        return None

    @staticmethod
    def generation_error(presentation, query: str, resources=None) -> str | None:
        assessment = EvidenceContextBuilder().assess(presentation, query, resources)
        if not assessment.has_validated_resources:
            record("generation_refusal", reason="no_validated_resources")
            return "No user-validated PDF is available for this production step."
        if not assessment.is_sufficient:
            record("generation_refusal", reason="insufficient_retrieved_evidence", score=assessment.best_score)
            return "Validated PDF resources do not contain sufficient verifiable evidence for this production step."
        return None

    @staticmethod
    def _message(state: GraphState, reason: str) -> str:
        language = state.user_profile.preferred_language
        messages = {
            "fr": {
                "general": "Je peux vous aider à cadrer la présentation et à préparer les ressources, mais je ne peux pas répondre à une question scientifique sans PDF fourni par l’utilisateur. Ajoutez un PDF puis utilisez l’analyse des ressources ou créez une présentation.",
                "missing": "Je ne peux pas produire une réponse scientifique sans PDF validé. Ajoutez une ressource pertinente, puis validez-la.",
                "insufficient": "Les ressources validées ne contiennent pas de preuve suffisamment pertinente et vérifiable pour répondre. Ajoutez un PDF plus adapté ou précisez la question.",
            },
            "ar": {
                "general": "يمكنني مساعدتك في تحديد إطار العرض وتحضير المصادر، لكن لا يمكنني الإجابة عن سؤال علمي من دون ملف PDF يقدمه المستخدم. أضف ملف PDF ثم استخدم تحليل المصادر أو أنشئ عرضاً.",
                "missing": "لا يمكنني تقديم إجابة علمية من دون ملف PDF موثّق من المستخدم. أضف مورداً مناسباً ثم اعتمده.",
                "insufficient": "لا تحتوي الموارد المعتمدة على دليل كافٍ وقابل للتحقق للإجابة. أضف ملف PDF أكثر ملاءمة أو وضّح السؤال.",
            },
            "en": {
                "general": "I can help frame the presentation and prepare resources, but I cannot answer a scientific question without a user-provided PDF. Add a PDF, then use resource analysis or create a presentation.",
                "missing": "I cannot provide a scientific answer without a user-validated PDF. Add a relevant resource, then validate it.",
                "insufficient": "The validated resources do not contain sufficiently relevant, verifiable evidence to answer this question. Add a more suitable PDF or clarify the question.",
            },
        }
        return messages.get(language, messages["en"])[reason]
