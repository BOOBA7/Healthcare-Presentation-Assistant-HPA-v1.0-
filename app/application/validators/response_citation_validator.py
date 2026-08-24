"""Verify source citations in non-slide PDF-grounded model responses."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.application.validators.evidence_provenance_validator import EvidenceProvenanceValidator
from app.domain.exceptions.validation_error import ValidationError
from app.domain.models.resource import Resource


_CITATION = re.compile(
    r"\[\[cite:\s*(?P<resource_id>[^|\]\s]+)\s*\|\s*p\.\s*"
    r"(?P<page>[1-9][0-9]*)\s*\|\s*(?P<excerpt>[^\]]+?)\s*\]\]",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class VerifiedResponseCitation:
    """Citation details derived from a response that passed PDF checks."""

    resource_id: str
    page: int
    evidence_excerpt: str


class ResponseCitationValidator:
    """Require exact resource, page and quoted-text evidence in an AI response."""

    def validate(self, text: str, resources: list[Resource]) -> list[VerifiedResponseCitation]:
        matches = list(_CITATION.finditer(text))
        if not matches:
            raise ValidationError(
                "The model response has no system-verifiable PDF citation. Please retry the request."
            )

        resources_by_id = {resource.id: resource for resource in resources}
        verified: list[VerifiedResponseCitation] = []
        for match in matches:
            resource_id = match.group("resource_id")
            page = int(match.group("page"))
            excerpt = match.group("excerpt").strip()
            if resource_id not in resources_by_id:
                raise ValidationError("The model response cites an unknown uploaded PDF resource.")
            if len(excerpt) < 12:
                raise ValidationError("The model response citation has no usable evidence excerpt.")
            resource = resources_by_id[resource_id]
            page_text = next(
                (
                    candidate.get("text")
                    for candidate in resource.extracted_pages
                    if candidate.get("page") == page
                ),
                None,
            )
            if not isinstance(page_text, str):
                raise ValidationError("The model response cites a PDF page that does not exist.")
            if EvidenceProvenanceValidator._normalize(excerpt) not in EvidenceProvenanceValidator._normalize(page_text):
                raise ValidationError("The model response evidence excerpt was not found on the cited PDF page.")
            verified.append(VerifiedResponseCitation(resource_id, page, excerpt))
        return verified
