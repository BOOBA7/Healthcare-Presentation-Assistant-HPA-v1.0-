"""Small platform endpoints independent from workflow implementation."""

from fastapi import APIRouter

from app.application.services.observability import snapshot as observability_snapshot


router = APIRouter(prefix="/api/v1", tags=["platform"])


@router.get("/health")
def health() -> dict[str, str]:
    """Versioned health endpoint for clients and CI smoke tests."""
    return {"status": "healthy", "api_version": "v1"}


@router.get("/observability/summary", tags=["observability"])
def observability_summary() -> dict[str, object]:
    """Return process-local counters without prompt or PDF content."""
    return {"counters": observability_snapshot()}
