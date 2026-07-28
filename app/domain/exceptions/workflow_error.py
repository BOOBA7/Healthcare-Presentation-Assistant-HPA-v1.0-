from app.domain.exceptions.domain_error import DomainError


class WorkflowError(DomainError):
    """Safe, user-facing error with a stable code for audit and UI handling."""

    def __init__(self, code: str, user_message: str, *, retryable: bool = False) -> None:
        super().__init__(user_message, code=code, retryable=retryable)
