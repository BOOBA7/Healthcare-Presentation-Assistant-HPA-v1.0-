import pytest

from app.ai.mappers.blueprint_mapper import BlueprintMapper
from app.ai.schemas.blueprint_schema import BlueprintSchema, SlideOutline as SchemaSlideOutline
from app.application.services.blueprint_structure import BlueprintStructurePolicy
from app.application.use_cases.create_presentation import CreatePresentationUseCase
from app.application.use_cases.workflow_steps import ValidateBlueprintWorkflowUseCase
from app.ai.workflows.graph_state import GraphState
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.blueprint import Blueprint
from app.domain.models.agenda import Agenda
from app.domain.models.slide_outline import SlideOutline
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.value_objects.presentation_context import PresentationContext


def _schema(source_ids: list[str] | None = None) -> BlueprintSchema:
    return BlueprintSchema(
        title="Synthetic blueprint",
        storytelling="Evidence before interpretation",
        learning_objectives=["Review synthetic evidence"],
        estimated_duration=10,
        slides=[
            SchemaSlideOutline(
                slide_number=3,
                slide_role="content",
                title="Evidence overview",
                objective="Explain the supplied result",
                key_message="The supplied source supports the planned message",
                supporting_source_ids=source_ids or ["resource-1"],
                planned_visual="A labelled comparison chart from the supplied values",
            )
        ],
        key_message="Use only supplied evidence",
    )


def test_blueprint_mapper_completes_every_reviewable_item_field():
    blueprint = BlueprintMapper().to_domain(_schema(), {"resource-1"})

    item = blueprint.slides[0]
    assert item.model_dump() == {
        "slide_number": 3,
        "slide_role": "content",
        "title": "Evidence overview",
        "objective": "Explain the supplied result",
        "key_message": "The supplied source supports the planned message",
        "supporting_source_ids": ["resource-1"],
        "planned_visual": "A labelled comparison chart from the supplied values",
        "is_validated": False,
        "reviewer_comments": None,
        "content_origin": "ai_generated",
        "original_ai_snapshot": None,
    }


def test_blueprint_mapper_refuses_an_invented_supporting_source():
    with pytest.raises(ValueError, match="unknown supporting resource identifiers: invented"):
        BlueprintMapper().to_domain(_schema(["invented"]), {"resource-1"})


def test_legacy_blueprint_item_loads_with_explicit_safe_defaults():
    item = SlideOutline.model_validate(
        {"slide_number": 1, "title": "Legacy", "objective": "Review", "key_message": "Message"}
    )

    assert item.supporting_source_ids == []
    assert item.planned_visual == "No visual planned"
    assert item.slide_role == "content"


def _structured_presentation() -> object:
    context = PresentationContext(
        topic="Synthetic evidence",
        audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE,
        language=Language.ENGLISH,
        duration_minutes=10,
        objective="Review supplied evidence",
        target_slide_count=6,
        special_instructions="Synthetic fixture only",
        professional_scope="Teaching within my specialty",
        is_multidisciplinary=False,
    )
    presentation = CreatePresentationUseCase().execute(context.topic, context)
    common = {"objective": "Review the plan", "planned_visual": "No visual planned", "is_validated": True}
    presentation.blueprint = Blueprint(
        title="Synthetic blueprint",
        learning_objective=context.objective,
        target_number_of_slides=6,
        storytelling="Evidence first",
        structure_version=1,
        slides=[
            SlideOutline(slide_number=1, slide_role="title", title="Title", key_message="Opening", **common),
            SlideOutline(slide_number=2, slide_role="agenda", title="Agenda", key_message="Plan", **common),
            SlideOutline(slide_number=3, slide_role="content", title="Evidence", key_message="Supported message", supporting_source_ids=["r1"], **common),
            SlideOutline(slide_number=4, slide_role="conclusion", title="Conclusion", key_message="Supported message", supporting_source_ids=["r1"], **common),
            SlideOutline(slide_number=5, slide_role="references", title="References", key_message="Sources", **common),
            SlideOutline(slide_number=6, slide_role="thank_you", title="Thank you", key_message="Questions", **common),
        ],
    )
    return presentation


def test_explicit_structure_counts_every_slide_against_the_requested_total():
    presentation = _structured_presentation()

    BlueprintStructurePolicy.require_valid(presentation)


def test_normal_structure_refuses_an_impossible_target_before_generation():
    presentation = _structured_presentation()
    presentation.context.target_slide_count = 5

    with pytest.raises(WorkflowError) as error:
        BlueprintStructurePolicy.require_viable_target(presentation)

    assert error.value.code == "DECK_TARGET_TOO_SMALL"


def test_structure_refuses_a_target_mismatch_and_out_of_order_roles():
    presentation = _structured_presentation()
    presentation.blueprint.slides.pop()
    with pytest.raises(WorkflowError) as mismatch:
        BlueprintStructurePolicy.require_valid(presentation)
    assert mismatch.value.code == "BLUEPRINT_TARGET_MISMATCH"

    presentation = _structured_presentation()
    presentation.blueprint.slides[1].slide_role = "content"
    with pytest.raises(WorkflowError) as invalid:
        BlueprintStructurePolicy.require_valid(presentation)
    assert invalid.value.code == "BLUEPRINT_STRUCTURE_INVALID"


def test_conclusion_cannot_introduce_a_new_assertion():
    presentation = _structured_presentation()
    presentation.blueprint.slides[3].key_message = "A new recommendation"

    with pytest.raises(WorkflowError) as error:
        BlueprintStructurePolicy.require_valid(presentation)

    assert error.value.code == "CONCLUSION_NEW_ASSERTION"


def test_blueprint_approval_requires_review_of_every_structural_item():
    presentation = _structured_presentation()
    presentation.agenda = Agenda(items=["Evidence"], is_validated=True)
    presentation.state.workflow_status = WorkflowStatus.AWAITING_BLUEPRINT_APPROVAL
    presentation.blueprint.slides[-1].is_validated = False
    state = GraphState(presentation=presentation)

    with pytest.raises(WorkflowError) as pending:
        ValidateBlueprintWorkflowUseCase().execute(state, approved=True)
    assert pending.value.code == "BLUEPRINT_ITEMS_PENDING"

    presentation.blueprint.slides[-1].is_validated = True
    result = ValidateBlueprintWorkflowUseCase().execute(state, approved=True)
    assert result.presentation.state.blueprint_validated
    assert result.presentation.state.workflow_status == WorkflowStatus.SLIDE_GENERATION
