"""Deterministic business rules for the presentation lifecycle.

The LLM may suggest a next action, but it cannot bypass these server-side
guards.  Keeping the rule set outside prompts makes the workflow testable and
auditable.
"""

from collections.abc import Iterable

from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.exceptions.invalid_transition import InvalidTransition
from app.domain.models.presentation import Presentation


class WorkflowPolicy:
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
