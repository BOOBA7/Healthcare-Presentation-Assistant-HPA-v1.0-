import pytest

from app.application.validators.evidence_provenance_validator import EvidenceProvenanceValidator
from app.ai.prompt_builders.evidence_context_builder import EvidenceContextBuilder
from app.application.use_cases.create_presentation import CreatePresentationUseCase
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.enums.resource_type import ResourceType
from app.domain.models.resource import Resource
from app.domain.models.slide import Slide
from app.domain.models.slide_outline import SlideOutline
from app.domain.value_objects.presentation_context import PresentationContext


def resource() -> Resource:
    return Resource(
        id="pdf-1",
        filename="guideline.pdf",
        title="Clinical guideline",
        file_type=ResourceType.PDF,
        extracted_text="Treatment should be individualized according to patient needs.",
        extracted_pages=[
            {
                "page": 2,
                "text": "Treatment should be individualized according to patient needs and clinical response.",
            }
        ],
        is_validated=True,
    )


def slide(reference: dict[str, object]) -> Slide:
    return Slide(slide_number=1, title="Treatment", reference_details=[reference])


def test_evidence_reference_is_verified_against_its_pdf_page():
    candidate = slide(
        {
            "title": "Clinical guideline",
            "resource_id": "pdf-1",
            "page": 2,
            "evidence_excerpt": "Treatment should be individualized according to patient needs",
        }
    )

    EvidenceProvenanceValidator().validate_slide(candidate, [resource()])

    assert candidate.evidence_verified


def test_arabic_evidence_excerpt_must_match_the_exact_pdf_page():
    arabic_resource = Resource(
        id="arabic-pdf",
        filename="guideline-ar.pdf",
        file_type=ResourceType.PDF,
        extracted_pages=[{"page": 4, "text": "يوصى بمراجعة الاستجابة للعلاج بانتظام."}],
        is_validated=True,
    )
    valid = slide(
        {"resource_id": "arabic-pdf", "page": 4, "evidence_excerpt": "مراجعة الاستجابة للعلاج"}
    )
    invalid = slide(
        {"resource_id": "arabic-pdf", "page": 4, "evidence_excerpt": "لا توجد هذه العبارة في المصدر"}
    )

    EvidenceProvenanceValidator().validate_slide(valid, [arabic_resource])
    with pytest.raises(ValueError, match="was not found"):
        EvidenceProvenanceValidator().validate_slide(invalid, [arabic_resource])


@pytest.mark.parametrize(
    "reference, message",
    [
        (
            {"resource_id": "unknown", "page": 2, "evidence_excerpt": "Treatment should be individualized"},
            "unknown resource ID",
        ),
        (
            {"resource_id": "pdf-1", "page": 7, "evidence_excerpt": "Treatment should be individualized"},
            "does not exist",
        ),
        (
            {"resource_id": "pdf-1", "page": 2, "evidence_excerpt": "This sentence does not occur in the PDF"},
            "was not found",
        ),
    ],
)
def test_invalid_evidence_reference_is_rejected(reference, message):
    with pytest.raises(ValueError, match=message):
        EvidenceProvenanceValidator().validate_slide(slide(reference), [resource()])


def test_retrieval_context_is_compact_and_keeps_page_metadata():
    context = PresentationContext(
        topic="Depression treatment",
        audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE,
        language=Language.ENGLISH,
        duration_minutes=10,
        objective="Review treatment options",
    )
    presentation = CreatePresentationUseCase().execute("Depression treatment", context)
    evidence = resource()
    evidence.extracted_pages = [
        {"page": 1, "text": "Background " * 1_000},
        {"page": 2, "text": "Depression treatment should be individualized according to clinical response."},
    ]
    presentation.resources = [evidence]
    outline = SlideOutline(
        slide_number=1,
        title="Treatment",
        objective="Review depression treatment",
        key_message="Treatment should be individualized",
    )

    retrieved = EvidenceContextBuilder().for_slide(presentation, outline)

    assert "SOURCE ID: pdf-1" in retrieved
    assert "PAGE: 2" in retrieved
    assert len(retrieved) <= EvidenceContextBuilder.max_characters
