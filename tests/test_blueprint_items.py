import pytest

from app.ai.mappers.blueprint_mapper import BlueprintMapper
from app.ai.schemas.blueprint_schema import BlueprintSchema, SlideOutline as SchemaSlideOutline
from app.domain.models.slide_outline import SlideOutline


def _schema(source_ids: list[str] | None = None) -> BlueprintSchema:
    return BlueprintSchema(
        title="Synthetic blueprint",
        storytelling="Evidence before interpretation",
        learning_objectives=["Review synthetic evidence"],
        estimated_duration=10,
        slides=[
            SchemaSlideOutline(
                slide_number=3,
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
