"""In-process asynchronous jobs with durable SQLite progress records."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import logging

from fastapi import HTTPException

from app.application.services.observability import record
from app.interfaces.storage.user_session_repository import UserSessionRepository


logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hpa-job")


def _job_error_message(exc: Exception) -> str:
    """Return the user-facing API message rather than a Python HTTP wrapper."""
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("detail") or "The operation could not be completed.")
        if isinstance(detail, str):
            return detail
    return str(exc)


def submit(
    repository: UserSessionRepository,
    user_id: str,
    job_id: str,
    domain: str,
    work: Callable[[Callable[[int, str], None]], dict[str, object]],
) -> None:
    """Schedule work and make each visible state durable for browser polling."""
    def progress(value: int, stage: str) -> None:
        repository.update_job(user_id, job_id, status="running", progress=value, stage=stage)
        record("async_job_progress", domain=domain, progress=value, stage=stage)

    def run() -> None:
        try:
            progress(10, "running")
            result = work(progress)
            repository.update_job(
                user_id, job_id, status="completed", progress=100, stage="completed", result=result
            )
            record("async_job_completed", domain=domain)
        except Exception as exc:  # The API returns safe details on the polling endpoint.
            logger.exception("Async job failed job_id=%s domain=%s", job_id, domain)
            repository.update_job(
                user_id,
                job_id,
                status="failed",
                progress=100,
                stage="failed",
                error_message=_job_error_message(exc),
            )
            record("async_job_failed", domain=domain, error_type=type(exc).__name__)

    _executor.submit(run)
