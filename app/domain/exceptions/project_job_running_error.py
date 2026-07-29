from app.domain.exceptions.domain_error import DomainError


class ProjectJobRunningError(DomainError):
    """Raised when a Project already has a state-writing job in progress."""

    default_code = "PROJECT_JOB_ALREADY_RUNNING"

    def __init__(self) -> None:
        super().__init__(
            "A job is already running for this Project. Wait for it to finish before starting another action.",
            retryable=True,
        )
