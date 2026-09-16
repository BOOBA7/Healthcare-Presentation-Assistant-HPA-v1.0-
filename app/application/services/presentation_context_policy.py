"""Human context gate. Legacy input remains readable, never silently approved."""

import hashlib
import json

from app.domain.models.conversation_context import ConversationContext
from app.domain.exceptions.workflow_error import WorkflowError


class PresentationContextPolicy:
    @staticmethod
    def digest(context):
        fields = ("topic", "audience", "language", "presentation_type", "duration_minutes", "objective", "target_slide_count",
                  "special_instructions", "professional_scope", "is_multidisciplinary")
        values = context.model_dump(mode="json")
        return hashlib.sha256(json.dumps({key: values[key] for key in fields},
                                        sort_keys=True).encode()).hexdigest()

    @classmethod
    def require(cls, presentation):
        if presentation is None:
            return
        context = presentation.context
        missing = ConversationContext(**context.model_dump()).missing_fields()
        if missing:
            raise WorkflowError("PRESENTATION_CONTEXT_REQUIRED", "Complete presentation context: " + ", ".join(missing))
        declaration = presentation.professional_scope_declaration
        if (not declaration or not declaration.actor_user_id or not declaration.confirmed_within_scope
                or declaration.context_digest != cls.digest(context)
                or declaration.is_multidisciplinary != context.is_multidisciplinary
                or (context.is_multidisciplinary and not declaration.confirmed_multidisciplinary)):
            raise WorkflowError("PRESENTATION_CONTEXT_REQUIRED", "Confirm your professional scope and multidisciplinary competence in the context form.")
