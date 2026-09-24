"""Deterministic rules for a complete, human-reviewable deck plan."""

from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.presentation import Presentation


class BlueprintStructurePolicy:
    """Validate explicit structure without trusting a model or an interface."""

    @staticmethod
    def require_viable_target(presentation: Presentation) -> int:
        target = presentation.context.target_slide_count
        if target is None or target < 6:
            raise WorkflowError(
                "DECK_TARGET_TOO_SMALL",
                "The target must be at least 6 slides to include title, Agenda, main content, conclusion, references and thank-you.",
            )
        return target

    @classmethod
    def require_valid(cls, presentation: Presentation) -> None:
        blueprint = presentation.blueprint
        if blueprint is None or blueprint.structure_version < 1:
            return  # Backward-compatible loading of plans created before phase 07.3.

        slides = blueprint.slides
        target = cls.require_viable_target(presentation)
        if len(slides) != target or blueprint.target_number_of_slides != target:
            raise WorkflowError(
                "BLUEPRINT_TARGET_MISMATCH",
                "The Blueprint must count every structural slide and match the requested total slide count.",
            )
        if [item.slide_number for item in slides] != list(range(1, target + 1)):
            raise WorkflowError(
                "BLUEPRINT_NUMBERING_INVALID",
                "Blueprint slide numbers must be consecutive and cover the complete deck.",
            )

        roles = [item.slide_role for item in slides]
        expected_edges = ["title", "agenda"]
        expected_tail = ["conclusion", "references", "thank_you"]
        if roles[:2] != expected_edges or roles[-3:] != expected_tail or any(
            role != "content" for role in roles[2:-3]
        ):
            raise WorkflowError(
                "BLUEPRINT_STRUCTURE_INVALID",
                "Use the normal order: title, Agenda, main content, conclusion, references and thank-you.",
            )

        evidence_items = [*slides[2:-3], slides[-3]]
        if any(not item.supporting_source_ids for item in evidence_items):
            raise WorkflowError(
                "BLUEPRINT_SOURCES_MISSING",
                "Every main-content and conclusion item needs a planned supporting source.",
            )

        conclusion = slides[-3]
        content_messages = {item.key_message.strip().casefold() for item in slides[2:-3]}
        if conclusion.key_message.strip().casefold() not in content_messages:
            raise WorkflowError(
                "CONCLUSION_NEW_ASSERTION",
                "The conclusion key message must repeat a reviewed main-content message and introduce no new assertion.",
            )
