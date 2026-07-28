"""Deterministic business rules for the presentation lifecycle.

The LLM may suggest a next action, but it cannot bypass these server-side
guards.  Keeping the rule set outside prompts makes the workflow testable and
auditable.
"""

from collections.abc import Iterable

from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.exceptions.invalid_transition import InvalidTransition


class WorkflowPolicy:
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
