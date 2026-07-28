class DomainError(ValueError):
    """Base class for safe, expected business-domain failures.

    Inheriting from ``ValueError`` preserves the existing API and interface
    error handling while giving domain failures a stable, machine-readable code.
    """

    default_code = "DOMAIN_ERROR"

    def __init__(self, user_message: str, *, code: str | None = None, retryable: bool = False) -> None:
        super().__init__(user_message)
        self.code = code or self.default_code
        self.user_message = user_message
        self.retryable = retryable
