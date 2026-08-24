from app.application.services.citation_presentation import (
    citation_display_details,
    format_citations_for_display,
)
from app.domain.enums.resource_type import ResourceType
from app.domain.models.resource import Resource


def _resource() -> Resource:
    return Resource(
        id="b1fb1dda-0b26-4716-9626-1a5acf30684b",
        filename="apa-guideline.pdf",
        title="APA Depression Guideline",
        file_type=ResourceType.PDF,
    )


def test_citation_display_uses_the_pdf_title_without_changing_technical_details():
    raw = "The panel evaluated treatments [b1fb1dda, p. 4]."

    displayed = format_citations_for_display(raw, [_resource()])
    details = citation_display_details(raw, [_resource()])

    assert displayed == "The panel evaluated treatments [APA Depression Guideline, p. 4]."
    assert details[0].resource_id == "b1fb1dda-0b26-4716-9626-1a5acf30684b"
    assert details[0].title == "APA Depression Guideline"
    assert details[0].pages == "4"


def test_verified_response_citation_hides_the_internal_excerpt_but_keeps_details():
    raw = "The panel evaluated treatments [[cite: b1fb1dda-0b26-4716-9626-1a5acf30684b | p. 4 | Exact PDF excerpt.]]."

    displayed = format_citations_for_display(raw, [_resource()])
    details = citation_display_details(raw, [_resource()])

    assert displayed == "The panel evaluated treatments [APA Depression Guideline, p. 4]."
    assert details[0].resource_id == "b1fb1dda-0b26-4716-9626-1a5acf30684b"
    assert details[0].pages == "4"
