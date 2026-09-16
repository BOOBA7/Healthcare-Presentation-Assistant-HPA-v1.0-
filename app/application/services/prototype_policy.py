"""Fail-closed public prototype policy; declarations are assertions, not anonymisation."""

import re

from app.core.config import get_settings
from app.domain.exceptions.workflow_error import WorkflowError


class PrototypePolicy:
    VERSION = "public-synthetic-v1"
    DISCLOSURE = (
        "Public/synthetic prototype only. Content (resources, prompts and generated content) "
        "is sent to the configured external model provider (OpenAI or Gemini). "
        "Patient cases, even anonymised or synthetic cases, and confidential professional "
        "documents are forbidden. Professional mode is unavailable. "
        "Your declaration is an assertion; HPA cannot guarantee anonymisation or detect all restricted content."
    )
    _restricted = re.compile(
        r"\b(?:patient[ -]case|case report|cas patient|cas clinique|clinical case|"
        r"confidential|confidentiel(?:le)?|professional documents?|documents? professionnels?|medical record|dossier m[eé]dical|"
        r"patient\s*(?:id|identifier)\s*[:#]|mrn\s*[:#])(?!\w)", re.IGNORECASE
    )

    @classmethod
    def mode(cls):
        if get_settings().execution_mode != "public_prototype":
            raise WorkflowError("PROFESSIONAL_MODE_UNAVAILABLE", "Only public prototype mode is available.")

    @classmethod
    def declaration(cls, value, *, patient_case_mode=False):
        cls.mode()
        if patient_case_mode or value not in ("public", "synthetic"):
            raise WorkflowError(
                "PROTOTYPE_DECLARATION_REQUIRED",
                "Declare public or synthetic non-patient-case content and acknowledge external processing before continuing. Professional and patient-case material is forbidden.",
            )

    @classmethod
    def screen(cls, value):
        """Conservative explicit-marker screening, never semantic classification."""
        cls.mode()
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("patient_case_mode", "patient_case_acknowledged", "professional_mode") and item:
                    cls.declaration(None, patient_case_mode=True)
                if key in ("data_classification", "prototype_declaration") and item is not None:
                    cls.declaration(item)
                if key == "execution_mode" and item != "public_prototype":
                    cls.declaration(None)
                cls.screen(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                cls.screen(item)
        elif isinstance(value, str) and cls._restricted.search(value):
            raise WorkflowError("PROTOTYPE_CONTENT_BLOCKED", "Possible patient-case or confidential professional content detected. Processing is blocked.")

    @classmethod
    def state(cls, state):
        cls.declaration(state.prototype_declaration, patient_case_mode=state.patient_case_mode or state.patient_case_acknowledged)
        cls.screen(state)

    @classmethod
    def presentation(cls, presentation):
        cls.declaration(presentation.prototype_declaration)
        cls.screen(presentation)
