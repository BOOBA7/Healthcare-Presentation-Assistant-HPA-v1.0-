"""Conservative privacy guardrails for de-identified patient-case Projects.

This is an identifier detector and workflow safeguard, not a certification of
HIPAA compliance or a formal de-identification determination.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.domain.exceptions.workflow_error import WorkflowError


class PatientCasePrivacyGuard:
    """Block obvious identifiers before patient-case content reaches an LLM."""

    _patterns = {
        "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
        "phone number": re.compile(r"(?<!\d)(?:\+?\d[\d .()/-]{7,}\d)(?!\d)"),
        "full date": re.compile(
            r"\b(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})\b"
        ),
        "medical record identifier": re.compile(
            r"\b(?:mrn|medical\s*record|patient\s*(?:id|identifier)|dossier\s*(?:m[eé]dical|patient)|"
            r"num[eé]ro\s*de\s*dossier|n°\s*(?:dossier|patient))\s*[:#-]?\s*[A-Z0-9-]{4,}\b",
            re.IGNORECASE,
        ),
        "social security identifier": re.compile(
            r"\b(?:ssn|social\s*security|num[eé]ro\s*de\s*s[eé]curit[eé]\s*sociale)\s*[:#-]?\s*[A-Z0-9 -]{4,}\b",
            re.IGNORECASE,
        ),
        "postal address": re.compile(
            r"\b\d{1,5}\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' -]{2,}\s+(?:street|st\.?|avenue|ave\.?|road|rd\.?|boulevard|blvd\.?|rue|route)\b",
            re.IGNORECASE,
        ),
    }

    def findings(self, text: str) -> list[str]:
        """Return identifier categories only; never retain or expose matched text."""
        if not text:
            return []
        return [label for label, pattern in self._patterns.items() if pattern.search(text)]

    def ensure_text_safe(self, text: str) -> None:
        findings = self.findings(text)
        if findings:
            raise WorkflowError(
                "PATIENT_IDENTIFIER_DETECTED",
                "Patient Case Mode detected possible identifying information "
                f"({', '.join(findings)}). Remove or generalize it before continuing.",
                retryable=False,
            )

    def ensure_texts_safe(self, values: Iterable[str]) -> None:
        for value in values:
            self.ensure_text_safe(value)

    def ensure_resource_safe(self, resource) -> None:
        self.ensure_texts_safe(
            value
            for value in (resource.filename, resource.title, resource.source, resource.extracted_text)
            if isinstance(value, str)
        )

    def ensure_state_safe(self, state) -> None:
        """Avoid enabling the mode over an already identifier-bearing Project."""
        values: list[str] = []
        values.extend(
            turn.text
            for turn in [*state.conversation_history, *state.resource_conversation_history]
            if isinstance(turn.text, str)
        )
        for message in state.messages:
            content = getattr(message, "content", "")
            if isinstance(content, str):
                values.append(content)
        self.ensure_texts_safe(values)
        for resource in state.resource_library:
            self.ensure_resource_safe(resource)
