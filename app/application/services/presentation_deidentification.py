"""Deterministic identifier minimisation for generated presentation content.

This is a defence-in-depth transformation, not a HIPAA Safe Harbor or GDPR
anonymisation certification. Original resources remain unchanged for audit and
local retrieval; only model context and generated presentation fields use the
transformed text.
"""

from __future__ import annotations

import re
from typing import Any


class PresentationDeidentification:
    """Replace common direct identifiers with stable, non-identifying labels."""

    _rules = (
        (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[EMAIL REMOVED]"),
        (re.compile(r"\bhttps?://\S+|\bwww\.\S+", re.I), "[URL REMOVED]"),
        (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP ADDRESS REMOVED]"),
        (re.compile(r"(?<!\w)\+?\d[\d .()/-]{7,}\d(?!\w)"), "[PHONE REMOVED]"),
        (re.compile(
            r"\b(?:mrn|medical\s*record|patient\s*(?:id|identifier)|dossier\s*(?:m[eé]dical|patient)|"
            r"num[eé]ro\s*de\s*dossier|n°\s*(?:dossier|patient)|ssn|social\s*security|"
            r"health\s*plan|account|certificate|licen[cs]e|device|serial|vehicle)"
            r"\s*(?:number|num[eé]ro|id)?\s*[:#-]?\s*[A-Z0-9][A-Z0-9 ./-]{2,}", re.I,
        ), "[IDENTIFIER REMOVED]"),
        (re.compile(
            r"\b(?:date\s+of\s+birth|birth\s+date|dob|date\s+de\s+naissance|n[eé]e?\s+le|"
            r"admission|discharge|death\s+date|date\s+de\s+d[eé]c[eè]s)\s*[:#-]?\s*"
            r"(?:\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}|\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4})", re.I,
        ), "[DATE REMOVED]"),
        (re.compile(
            r"\b\d{1,5}\s+(?:(?:rue|avenue|boulevard|route)\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' -]{1,50}|"
            r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' -]{1,50}\s+(?:street|st\.?|avenue|ave\.?|road|rd\.?|boulevard|blvd\.?))\b",
            re.I,
        ), "[ADDRESS REMOVED]"),
        (re.compile(r"\b(?:name|patient\s+name|nom|pr[eé]nom)\s*:\s*[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' -]{1,80}", re.I),
         "[NAME REMOVED]"),
        (re.compile(r"\b(?:age|[âa]g[eé]e?)\s*:\s*(?:9\d|1\d{2})\b", re.I), "[AGE 90 OR OLDER]"),
    )

    @classmethod
    def text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        result = value
        for pattern, replacement in cls._rules:
            result = pattern.sub(replacement, result)
        return result

    @classmethod
    def value(cls, value: Any) -> Any:
        """Recursively transform text in a generated structured payload."""
        if isinstance(value, str):
            return cls.text(value)
        if isinstance(value, list):
            return [cls.value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(cls.value(item) for item in value)
        if isinstance(value, dict):
            return {key: cls.value(item) for key, item in value.items()}
        return value
