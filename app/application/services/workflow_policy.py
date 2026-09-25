"""Deterministic business rules for the presentation lifecycle.

The LLM may suggest a next action, but it cannot bypass these server-side
guards.  Keeping the rule set outside prompts makes the workflow testable and
auditable.
"""

from collections.abc import Iterable

from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.exceptions.invalid_transition import InvalidTransition
from app.domain.models.presentation import Presentation
from app.domain.exceptions.workflow_error import WorkflowError


class WorkflowPolicy:
    @staticmethod
    def require_export_eligible(presentation: Presentation) -> None:
        """Re-evaluate every export rule independently from workflow status."""
        if not presentation.slides:
            raise WorkflowError("SLIDES_NOT_GENERATED", "Generate presentation slides before export.")
        for slide in presentation.slides:
            if not slide.is_validated or not slide.approved_by or not slide.approved_at:
                raise WorkflowError(
                    "SLIDE_APPROVAL_REQUIRED",
                    f"Slide {slide.slide_number} requires an audited human approval before export.",
                )
            if slide.content_classification == "medical" and (
                slide.source_missing
                or (slide.content_origin != "ai_generated" and not slide.evidence_verified)
            ):
                raise WorkflowError(
                    "SLIDE_EVIDENCE_REQUIRED",
                    f"Slide {slide.slide_number} requires approved claim evidence before export.",
                )
            if slide.speaker_notes and (
                slide.speaker_note is None
                or not slide.speaker_note.is_approved
                or not slide.speaker_note.approved_by
                or not slide.speaker_note.approved_at
            ):
                raise WorkflowError(
                    "SPEAKER_NOTE_APPROVAL_REQUIRED",
                    f"Slide {slide.slide_number} speaker notes require audited human approval before export.",
                )

    @staticmethod
    def requires_resource_validation(presentation: Presentation | None) -> bool:
        """Return whether a selected evidence set awaits the human approval gate.

        This is a business-state rule shared by every interface.  It must not
        depend on a previous LLM error message, because users may attach a PDF
        before asking the model to generate a blueprint.
        """
        return bool(
            presentation is not None
            and presentation.resources
            and not presentation.state.resources_validated
            and presentation.state.workflow_status == WorkflowStatus.AWAITING_RESOURCE_VALIDATION
        )

    @staticmethod
    def require_status(
        current: WorkflowStatus,
        allowed: Iterable[WorkflowStatus],
        action: str,
    ) -> None:
        allowed_statuses = tuple(allowed)
        if current not in allowed_statuses:
            raise InvalidTransition(
                current_status=current.value,
                action=action,
                allowed_statuses=(status.value for status in allowed_statuses),
            )
