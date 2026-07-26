"""Deterministic business rules for the presentation lifecycle.

The LLM may suggest a next action, but it cannot bypass these server-side
guards.  Keeping the rule set outside prompts makes the workflow testable and
auditable.
"""

from collections.abc import Iterable

from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.exceptions.workflow_error import WorkflowError


class WorkflowPolicy:
    @staticmethod
    def require_status(
        current: WorkflowStatus,
        allowed: Iterable[WorkflowStatus],
        action: str,
    ) -> None:
        allowed_statuses = tuple(allowed)
        if current not in allowed_statuses:
            raise WorkflowError(
                "INVALID_WORKFLOW_TRANSITION",
                f"Cannot {action} while the workflow is '{current.value}'.",
            )
