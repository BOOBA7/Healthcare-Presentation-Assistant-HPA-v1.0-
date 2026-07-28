from app.domain.exceptions.domain_error import DomainError


class ValidationError(DomainError):
    """Raised when deterministic validation rejects domain data."""

    default_code = "DOMAIN_VALIDATION_FAILED"
