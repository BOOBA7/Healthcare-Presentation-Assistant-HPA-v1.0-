import pytest

from app.application.validators.evidence_provenance_validator import EvidenceProvenanceValidator
from app.ai.prompt_builders.evidence_context_builder import EvidenceContextBuilder
from app.application.use_cases.create_presentation import CreatePresentationUseCase
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.enums.resource_type import ResourceType
from app.domain.enums.evidence_context_mode import EvidenceContextMode
from app.domain.models.resource import Resource
from app.domain.models.resource_chunk import ResourceChunk
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


def test_retrieval_prefers_normalized_sqlite_chunks_over_in_state_pdf_pages():
    evidence = resource()
    # Presentation selections intentionally do not carry full PDF pages after
    # resource-library normalization. Retrieval must still work from storage.
    evidence.extracted_pages = []

    context = EvidenceContextBuilder().for_resources(
        [evidence],
        "individualized treatment",
        [
            ResourceChunk(
                resource_id="pdf-1",
                page=2,
                position=0,
                title="Clinical guideline",
                text="Treatment should be individualized according to patient needs.",
            )
        ],
    )

    assert "SOURCE ID: pdf-1" in context
    assert "PAGE: 2" in context


def test_direct_bounded_context_remains_source_bound_without_bm25_ranking():
    context = PresentationContext(
        topic="Depression treatment",
        audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE,
        language=Language.ENGLISH,
        duration_minutes=10,
        objective="Review treatment options",
    )
    presentation = CreatePresentationUseCase().execute(
        "Depression treatment",
        context,
        evidence_context_mode=EvidenceContextMode.DIRECT_BOUNDED,
    )
    evidence = resource()
    chunks = [
        ResourceChunk(
            resource_id="pdf-1",
            page=1,
            position=0,
            title="Clinical guideline",
            text="Background and methods for this clinical guideline.",
        ),
        ResourceChunk(
            resource_id="pdf-1",
            page=2,
            position=0,
            title="Clinical guideline",
            text="Depression treatment should be individualized according to clinical response.",
        ),
    ]

    retrieved = EvidenceContextBuilder().for_resources(
        [evidence],
        "individualized depression treatment",
        chunks,
        EvidenceContextMode.DIRECT_BOUNDED,
    )
    assessment = EvidenceContextBuilder().assess(
        presentation,
        "individualized depression treatment",
        [evidence],
        chunks,
    )

    assert "PAGE: 1" in retrieved
    assert "PAGE: 2" in retrieved
    assert assessment.is_sufficient


def test_bm25_and_direct_apply_the_same_single_passage_evidence_rule():
    """Direct mode must not pass by pooling partial terms across two passages."""
    context = PresentationContext(
        topic="Depression treatment",
        audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE,
        language=Language.ENGLISH,
        duration_minutes=10,
        objective="Review treatment options",
    )
    resource = Resource(
        id="pdf-parity",
        filename="parity.pdf",
        file_type=ResourceType.PDF,
        is_validated=True,
    )
    chunks = [
        ResourceChunk(
            resource_id="pdf-parity",
            page=1,
            position=0,
            title="Parity source",
            text="Depression background is described here.",
        ),
        ResourceChunk(
            resource_id="pdf-parity",
            page=2,
            position=0,
            title="Parity source",
            text="Treatment considerations are described separately.",
        ),
    ]
    query = "depression treatment pharmacotherapy"
    builder = EvidenceContextBuilder()

    bm25 = CreatePresentationUseCase().execute("BM25", context, evidence_context_mode=EvidenceContextMode.BM25)
    direct = CreatePresentationUseCase().execute(
        "Direct",
        context,
        evidence_context_mode=EvidenceContextMode.DIRECT_BOUNDED,
    )

    bm25_assessment = builder.assess(bm25, query, [resource], chunks)
    direct_assessment = builder.assess(direct, query, [resource], chunks)

    assert not bm25_assessment.is_sufficient
    assert not direct_assessment.is_sufficient
    assert bm25_assessment.required_matches == direct_assessment.required_matches == 2
    assert bm25_assessment.selected_locations
    assert direct_assessment.selected_locations
