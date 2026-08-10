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
    _planning_or_navigation = re.compile(
        r"\b(presentation|presentations|slide|slides|blueprint|agenda|outline|project|workflow|"
        r"présentation|diapositive|diapositives|projet|ordre du jour|workflow|"
        r"عرض|شرائح|شريحة|مشروع|مخطط|أجندة)\b",
        re.IGNORECASE,
    )
    _presentation_context_turn = re.compile(
        r"\b(presentation|presentations|présentation|présentations|fmc|formation\s+m[eé]dicale\s+continue|"
        r"workshop|atelier|lecture|symposium|webinar|webinaire|congress|congr[eè]s|"
        r"audience|public|m[eé]decin(?:s)?|general practitioner|g[eé]n[eé]raliste(?:s)?|"
        r"r[eé]sident(?:s)?|specialist(?:s)?|sp[eé]cialiste(?:s)?|pharmacist(?:s)?|pharmacien(?:s)?|"
        r"duration|dur[eé]e|minute(?:s)?|objectif|objective|mise\s+[àa]\s+jour|update|"
        r"knowledge|connaissance(?:s)?|formation|training|resource(?:s)?|ressource(?:s)?|"
        r"source(?:s)?|document(?:s)?|pdf|عرض|تقديمي|شرائح|جمهور|مدة|دقائق|هدف|مصدر|مراجع)\b",
        re.IGNORECASE,
    )

    @classmethod
    def requires_evidence(cls, user_message: str) -> bool:
        """Return whether a chat turn needs user-PDF evidence before LLM use.

        This is deliberately an allow-list, not a medical-keyword detector.
        A factual question can be expressed with an unlimited number of terms,
        languages, abbreviations, or short follow-ups (for example, “What
        about CBT?”).  Only clearly non-factual social, profile, and workflow
        coordination turns may reach the LLM without retrieved PDF passages.
        """
        return not (
            cls._social_only.match(user_message)
            or cls._personal_context.search(user_message)
            or (
                cls._explicit_action.search(user_message)
                and cls._planning_or_navigation.search(user_message)
            )
        )

    @classmethod
    def is_presentation_context_turn(cls, user_message: str) -> bool:
        """Recognise human workflow metadata without treating it as a scientific query.

        A user must be able to create a presentation through chat before PDFs
        are selected and validated.  This narrow allow-list permits the model
        to collect *presentation metadata* in GENERAL mode; the system prompt
        still prohibits factual scientific answers in that mode.
        """
        return bool(cls._presentation_context_turn.search(user_message))

    def block_reason(self, state: GraphState, user_message: str) -> str | None:
        """Return a safe user message, or ``None`` when the LLM may answer."""
        presentation = state.presentation
        mode = ConversationMode.PRODUCTION if presentation is not None else state.conversation_mode
        if mode == ConversationMode.GENERAL and self.is_presentation_context_turn(user_message):
            return None
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
        assessment = EvidenceContextBuilder().assess(presentation, query, resources, chunks)
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
