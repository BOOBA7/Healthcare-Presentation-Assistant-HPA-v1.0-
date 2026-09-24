from app.application.services.presentation_deidentification import PresentationDeidentification
from app.ai.prompt_builders.evidence_context_builder import EvidenceChunk, EvidenceContextBuilder


def test_direct_identifiers_are_removed_from_generated_content_surfaces():
    source = (
        "Name: Alice Example; Date of birth: 1990-01-02; "
        "MRN: PAT-12345; alice@example.org; +33 6 12 34 56 78"
    )
    protected = PresentationDeidentification.text(source)
    assert "Alice Example" not in protected
    assert "1990-01-02" not in protected
    assert "PAT-12345" not in protected
    assert "alice@example.org" not in protected
    assert "+33 6 12 34 56 78" not in protected
    assert "[NAME REMOVED]" in protected


def test_untrusted_evidence_is_deidentified_before_model_context():
    chunk = EvidenceChunk(
        resource_id="resource-1", page=1, title="Case for alice@example.org",
        position=0, text="Name: Alice Example; MRN: PAT-12345", terms=("case",),
    )
    context = EvidenceContextBuilder()._format_chunk(chunk)
    assert "alice@example.org" not in context
    assert "Alice Example" not in context
    assert "PAT-12345" not in context
    assert "REMOVED" in context


def test_recursive_generated_payload_is_deidentified_without_mutating_structure():
    payload = {
        "title": "Patient ID: ABC-9876",
        "notes": ["Contact alice@example.org", {"address": "12 rue Exemple"}],
        "count": 2,
    }
    protected = PresentationDeidentification.value(payload)
    assert protected["count"] == 2
    assert "ABC-9876" not in protected["title"]
    assert "alice@example.org" not in protected["notes"][0]
    assert "12 rue Exemple" not in protected["notes"][1]["address"]
