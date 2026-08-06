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

    def findings(self, text: str, *, include_dates: bool = True) -> list[str]:
        """Return identifier categories only; never retain or expose matched text."""
        if not text:
            return []

        findings: list[str] = []
        for label, pattern in self._patterns.items():
            if label == "full date" and not include_dates:
                continue
            for match in pattern.finditer(text):
                # Numeric dates can otherwise look like phone numbers to a
                # broad phone-number pattern. A publication date in a
                # guideline is not, by itself, patient-identifying data.
                if label == "phone number" and self._patterns["full date"].fullmatch(match.group()):
                    continue
                findings.append(label)
                break
        return findings

    def ensure_text_safe(self, text: str, *, include_dates: bool = True) -> None:
        findings = self.findings(text, include_dates=include_dates)
        if findings:
            raise WorkflowError(
                "PATIENT_IDENTIFIER_DETECTED",
                "Patient Case Mode detected possible identifying information "
                f"({', '.join(findings)}). Remove or generalize it before continuing.",
                retryable=False,
            )

    def ensure_texts_safe(self, values: Iterable[str], *, include_dates: bool = True) -> None:
        for value in values:
            self.ensure_text_safe(value, include_dates=include_dates)

    def ensure_resource_safe(self, resource) -> None:
        """Screen PDF text for high-confidence identifiers only.

        Scientific PDFs commonly contain publication dates.  A date alone is
        insufficient to identify a patient, so it must not make Patient Case
        Mode unusable for normal guidelines or articles. Obvious identifiers
        such as emails, phone numbers, record numbers and addresses remain
        blocked anywhere in an uploaded resource.
        """
        self.ensure_texts_safe(
            (
                value
                for value in (resource.filename, resource.title, resource.source, resource.extracted_text)
                if isinstance(value, str)
            ),
            include_dates=False,
        )

    def ensure_state_safe(self, state) -> None:
        """Avoid enabling the mode over an already identifier-bearing Project."""
        values: list[str] = []
        values.extend(
            turn.text
            for turn in [*state.conversation_history, *state.resource_conversation_history]
            if turn.role == "user" and isinstance(turn.text, str)
        )
        for message in state.messages:
            content = getattr(message, "content", "")
            if getattr(message, "type", "") == "human" and isinstance(content, str):
                values.append(content)
        context = state.conversation_context
        values.extend(
            value
            for value in (context.topic, context.objective)
            if isinstance(value, str)
        )
        presentation = state.presentation
        if presentation is not None:
            values.extend(
                value
                for value in (
                    presentation.title,
                    presentation.professional_scope,
                    presentation.context.topic,
                    presentation.context.objective,
                )
                if isinstance(value, str)
            )
            if presentation.blueprint is not None:
                blueprint = presentation.blueprint
                values.extend(
                    value
                    for value in (
                        blueprint.title,
                        blueprint.learning_objective,
                        blueprint.storytelling,
                        blueprint.reviewer_comments,
                        *blueprint.sections,
                    )
                    if isinstance(value, str)
                )
                for outline in blueprint.slides:
                    if outline.content_origin != "ai_generated":
                        values.extend(
                            value
                            for value in (
                                outline.title,
                                outline.objective,
                                outline.key_message,
                                outline.reviewer_comments,
                            )
                            if isinstance(value, str)
                        )
            for slide in presentation.slides:
                if slide.content_origin != "ai_generated":
                    values.extend(
                        value
                        for value in (
                            slide.title,
                            slide.objective,
                            slide.content,
                            slide.speaker_notes,
                            slide.reviewer_comments,
                            *slide.key_messages,
                        )
                        if isinstance(value, str)
                    )
        self.ensure_texts_safe(values)
        for resource in state.resource_library:
            self.ensure_resource_safe(resource)
