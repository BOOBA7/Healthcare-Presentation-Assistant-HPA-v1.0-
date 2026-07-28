from collections.abc import Iterable

from app.domain.exceptions.workflow_error import WorkflowError


class InvalidTransition(WorkflowError):
    """Raised when an action is not allowed by the workflow lifecycle."""

    def __init__(self, *, current_status: str, action: str, allowed_statuses: Iterable[str]) -> None:
        self.current_status = current_status
        self.action = action
        self.allowed_statuses = tuple(allowed_statuses)
        super().__init__(
            "INVALID_WORKFLOW_TRANSITION",
            f"Cannot {action} while the workflow is '{current_status}'.",
        )
