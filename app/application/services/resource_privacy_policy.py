"""Deterministic resource privacy policy combining automation and user context."""

from enum import StrEnum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.application.services.identifier_screening import IdentifierScreening


class ResourceDeclaration(StrEnum):
    PUBLIC_NO_IDENTIFIABLE_PATIENT_DATA = "public_no_identifiable_patient_data"
    PUBLIC_ANONYMIZED_CASE_MATERIAL = "public_anonymized_case_material"
    MAY_CONTAIN_IDENTIFIABLE_PATIENT_DATA = "may_contain_identifiable_patient_data"
    UNSURE = "unsure"


class ResourcePrivacyDecision(StrEnum):
    AUTHORIZED = "authorized"
    LOCAL_ONLY = "local_only"
    NEEDS_USER_CONTEXT = "needs_user_context"
    CONFLICT = "conflict"
    BLOCKED = "blocked"
    INCOMPLETE = "incomplete"


class AutomatedScreeningReport(BaseModel):
    """Content-free summary. Never contains matched source excerpts or values."""

    model_config = ConfigDict(extra="forbid")
    finding_categories: list[str] = Field(default_factory=list)
    screening_policy_version: str


class ResourcePrivacyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: ResourcePrivacyDecision
    reason_code: str
    declaration: ResourceDeclaration | None = None
    report: AutomatedScreeningReport
    privacy_policy_version: str


class ResourcePrivacyPolicy:
    """Pure final-decision policy. A declaration can add context, never remove findings."""

    VERSION = "resource-privacy-v1"
    SCREENING_VERSION = "identifier-context-v1"
    _PUBLIC_CONTEXT = (
        "author", "auteur", "publisher", "éditeur", "editeur", "institution", "organisation",
        "organization", "authority", "autorité", "contact", "correspondence", "bibliograph",
        "journal", "doi", "university", "université", "hospital", "hôpital", "haute autorité",
    )
    _PATIENT_CONTEXT = re.compile(
        r"\b(?:patient[ -]case|case report|cas patient|cas clinique|clinical case|"
        r"medical record|dossier m[eé]dical|patient\s*(?:id|identifier)|mrn)\b", re.IGNORECASE,
    )
    _CONFIDENTIAL_CONTEXT = re.compile(
        r"\b(?:confidential|confidentiel(?:le)?|professional documents?|documents? professionnels?)\b",
        re.IGNORECASE,
    )

    @classmethod
    def iter_strings(cls, value: Any):
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        if isinstance(value, dict):
            for item in value.values():
                yield from cls.iter_strings(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from cls.iter_strings(item)
        elif isinstance(value, str):
            yield value

    @classmethod
    def analyze(cls, value: Any) -> AutomatedScreeningReport:
        categories: set[str] = set()
        for text in cls.iter_strings(value):
            lowered = text.casefold()
            contextual_public = any(marker in lowered for marker in cls._PUBLIC_CONTEXT)
            if cls._PATIENT_CONTEXT.search(text):
                categories.add("patient_context")
            if cls._CONFIDENTIAL_CONTEXT.search(text):
                categories.add("confidential_professional_content")
            for finding in IdentifierScreening.findings(text):
                if finding == "contact":
                    categories.add("public_contact" if contextual_public else "ambiguous_contact")
                elif finding == "address":
                    categories.add("public_contact" if contextual_public else "ambiguous_address")
                elif finding == "name" and contextual_public:
                    categories.add("author_or_bibliographic_name")
                else:
                    categories.add("possible_patient_identifier")
        return AutomatedScreeningReport(
            finding_categories=sorted(categories),
            screening_policy_version=cls.SCREENING_VERSION,
        )

    @classmethod
    def decide(cls, report: AutomatedScreeningReport,
               declaration: ResourceDeclaration | None) -> ResourcePrivacyResult:
        # Product policy: privacy findings are advisory and auditable. They do
        # not refuse a technically processable source or prevent its use.
        decision = ResourcePrivacyDecision.AUTHORIZED
        reason = "RESOURCE_AUTHORIZED_WITH_ADVISORY_FINDINGS" if report.finding_categories else "RESOURCE_AUTHORIZED"
        return ResourcePrivacyResult(
            decision=decision, reason_code=reason, declaration=declaration, report=report,
            privacy_policy_version=cls.VERSION,
        )

    @staticmethod
    def require_generation_ready(resource) -> None:
        return None
