class WorkflowError(ValueError):
    """Safe, user-facing error with a stable code for audit and UI handling."""

    def __init__(self, code: str, user_message: str, *, retryable: bool = False) -> None:
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.retryable = retryable
