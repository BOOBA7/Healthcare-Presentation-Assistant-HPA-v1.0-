"""Fail-closed public prototype policy; declarations are assertions, not anonymisation."""

import re

from app.application.services.identifier_screening import IdentifierScreening
from app.core.config import get_settings
from app.domain.exceptions.workflow_error import WorkflowError


class PrototypePolicy:
    VERSION = "public-synthetic-v1"
    DISCLOSURE = (
        "Public/synthetic prototype only. Content (resources, prompts and generated content) "
        "is sent to the configured external model provider (OpenAI or Gemini). "
        "Privacy findings on uploaded resources are advisory and do not prevent their use. "
        "The authenticated user is responsible for having authority to process every uploaded resource; "
        "HPA does not certify HIPAA compliance or de-identification. "
        "Professional mode is unavailable. "
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
            if hasattr(value, "metadata") and hasattr(value, "extracted_pages") and hasattr(value, "file_type"):
                from app.application.services.source_screening import SourceScreening
                SourceScreening.resource(value, require_text=True)
                return
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
        elif isinstance(value, str):
            if cls._restricted.search(value):
                raise WorkflowError("PROTOTYPE_CONTENT_BLOCKED", "Possible patient-case or confidential professional content detected. Processing is blocked.")
            IdentifierScreening.screen(value)

    @classmethod
    def screen_public_source(cls, value, *, resource_declaration=None,
                             institutional_contacts_confirmed=False):
        """Screen source material while routing contact-only findings to human review.

        Names, medical identifiers, dates of birth and restricted-content markers remain
        hard failures. A phone, email or postal address may pass only after the user has
        explicitly confirmed that it belongs to a public author, publisher or institution.
        """
        from app.application.services.resource_privacy_policy import (
            ResourceDeclaration, ResourcePrivacyDecision, ResourcePrivacyPolicy,
        )
        cls.mode()
        if institutional_contacts_confirmed and resource_declaration is None:
            resource_declaration = ResourceDeclaration.PUBLIC_NO_IDENTIFIABLE_PATIENT_DATA
        if resource_declaration is not None and not isinstance(resource_declaration, ResourceDeclaration):
            try:
                resource_declaration = ResourceDeclaration(resource_declaration)
            except ValueError:
                raise WorkflowError("RESOURCE_DECLARATION_INVALID", "Select a valid resource classification.") from None
        report = ResourcePrivacyPolicy.analyze(value)
        result = ResourcePrivacyPolicy.decide(report, resource_declaration)
        if result.decision == ResourcePrivacyDecision.NEEDS_USER_CONTEXT:
            raise WorkflowError(result.reason_code, "Classify this resource before importing it; contextual identifying information was detected.")
        if result.decision == ResourcePrivacyDecision.CONFLICT:
            raise WorkflowError(result.reason_code, "The declaration conflicts with possible patient-identifying information detected by screening.")
        if result.decision == ResourcePrivacyDecision.BLOCKED:
            message = ("Possible identifying information detected. Remove identifiers before continuing; automated checks cannot guarantee anonymisation."
                       if result.reason_code == "POSSIBLE_IDENTIFIER_DETECTED"
                       else "This resource classification is not allowed in public prototype mode.")
            raise WorkflowError(result.reason_code, message)
        return result

    @classmethod
    def state(cls, state):
        cls.declaration(state.prototype_declaration, patient_case_mode=state.patient_case_mode or state.patient_case_acknowledged)
        cls.screen_state_content(state, require_source_reviews=True)

    @classmethod
    def screen_state_content(cls, state, *, require_source_reviews: bool) -> None:
        """Screen project-authored content separately from reviewed source contacts."""
        payload = state.model_dump()
        resources = list(state.resource_library)
        payload["resource_library"] = []
        if payload.get("presentation"):
            payload["presentation"]["resources"] = []
            if state.presentation is not None:
                resources.extend(state.presentation.resources)
        cls.screen(payload)
        from app.application.services.source_screening import SourceScreening
        seen = set()
        for resource in resources:
            if resource.id not in seen:
                SourceScreening.resource(
                    resource,
                    require_text=True,
                    require_contact_review=require_source_reviews,
                )
                seen.add(resource.id)

    @classmethod
    def presentation(cls, presentation):
        cls.declaration(presentation.prototype_declaration)
        cls.screen(presentation)
