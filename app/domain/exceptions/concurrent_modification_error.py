from app.domain.exceptions.domain_error import DomainError


class ConcurrentModificationError(DomainError):
    """Raised when a Project changed after the caller loaded it."""

    default_code = "PROJECT_VERSION_CONFLICT"

    def __init__(self) -> None:
        super().__init__(
            "This Project changed in another operation. Reload it and retry your action.",
            retryable=True,
        )
