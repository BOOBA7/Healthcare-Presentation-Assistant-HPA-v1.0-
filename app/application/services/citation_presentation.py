"""Display-only labels for model citations without changing the audit record."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.domain.models.resource import Resource


_CITATION_PATTERN = re.compile(
    r"\[([0-9a-zA-Z][0-9a-zA-Z-]{3,})\s*,\s*p\.\s*([0-9]+(?:\s*,\s*[0-9]+)*)\]"
)
_VERIFIED_RESPONSE_CITATION_PATTERN = re.compile(
    r"\[\[cite:\s*([^|\]\s]+)\s*\|\s*p\.\s*([0-9]+)\s*\|\s*[^\]]+?\s*\]\]",
    re.IGNORECASE,
)
_RESOURCE_IDENTIFIER_PATTERN = re.compile(
    r"(?<![0-9a-fA-F])"
    r"([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}|[0-9a-fA-F]{8})"
    r"(?![0-9a-fA-F])"
)


@dataclass(frozen=True)
class CitationDisplayDetail:
    """Technical reference retained behind a human-readable citation label."""

    resource_id: str
    title: str
    pages: str | None = None


def format_citations_for_display(text: str, resources: list[Resource]) -> str:
    """Replace an internal resource identifier with its PDF title for the UI.

    The input is intentionally never mutated or persisted. SQLite therefore
    retains the exact model response and its resource identifiers for audit.
    """
    resource_map = _resource_map(resources)

    def replace_citation(match: re.Match[str]) -> str:
        resource_id, pages = match.groups()
        resource = _find_resource(resource_id, resource_map)
        if resource is None:
            return match.group(0)
        return f"[{_display_title(resource)}, p. {pages}]"

    formatted = _VERIFIED_RESPONSE_CITATION_PATTERN.sub(
        lambda match: (
            f"[{_display_title(resource)}, p. {match.group(2)}]"
            if (resource := _find_resource(match.group(1), resource_map)) is not None
            else match.group(0)
        ),
        text,
    )
    formatted = _CITATION_PATTERN.sub(replace_citation, formatted)

    def replace_identifier(match: re.Match[str]) -> str:
        resource = _find_resource(match.group(1), resource_map)
        return _display_title(resource) if resource is not None else match.group(0)

    return _RESOURCE_IDENTIFIER_PATTERN.sub(replace_identifier, formatted)


def citation_display_details(text: str, resources: list[Resource]) -> list[CitationDisplayDetail]:
    """Return the hidden-but-accessible technical metadata for visible citations."""
    resource_map = _resource_map(resources)
    details: list[CitationDisplayDetail] = []
    seen: set[tuple[str, str | None]] = set()

    def add(resource_id: str, pages: str | None = None) -> None:
        resource = _find_resource(resource_id, resource_map)
        if resource is None:
            return
        key = (resource.id, pages)
        if key not in seen:
            seen.add(key)
            details.append(CitationDisplayDetail(resource.id, _display_title(resource), pages))

    for match in _CITATION_PATTERN.finditer(text):
        add(match.group(1), match.group(2))
    for match in _VERIFIED_RESPONSE_CITATION_PATTERN.finditer(text):
        add(match.group(1), match.group(2))
    for match in _RESOURCE_IDENTIFIER_PATTERN.finditer(text):
        add(match.group(1))
    return details


def _resource_map(resources: list[Resource]) -> dict[str, Resource]:
    return {resource.id: resource for resource in resources}


def _find_resource(identifier: str, resources: dict[str, Resource]) -> Resource | None:
    if identifier in resources:
        return resources[identifier]
    return next((resource for resource_id, resource in resources.items() if resource_id.startswith(identifier)), None)


def _display_title(resource: Resource) -> str:
    return resource.title or resource.filename
