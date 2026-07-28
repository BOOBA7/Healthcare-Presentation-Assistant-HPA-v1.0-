"""Small dependency-free observability layer for local and production deployments."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
import json
import logging
from threading import Lock
from time import perf_counter
from typing import TypeVar


logger = logging.getLogger("hpa.observability")
_counts: Counter[str] = Counter()
_lock = Lock()
T = TypeVar("T")


def prompt_size(value: object) -> int:
    """Count prompt characters without retaining or logging source text."""
    to_messages = getattr(value, "to_messages", None)
    if callable(to_messages):
        return sum(prompt_size(getattr(message, "content", "")) for message in to_messages())
    if isinstance(value, str):
        return len(value)
    if isinstance(value, list):
        return sum(prompt_size(item) for item in value)
    if isinstance(value, dict):
        return sum(prompt_size(item) for item in value.values())
    return len(str(value))


def record(event: str, **attributes: object) -> None:
    """Emit structured, source-text-free telemetry to the application logs."""
    with _lock:
        _counts[event] += 1
    logger.info("observability=%s", json.dumps({"event": event, **attributes}, default=str, sort_keys=True))


def observe_llm_call(stage: str, prompt: object, invoke: Callable[[], T]) -> T:
    """Measure a model invocation and record duration, prompt size and errors."""
    started_at = perf_counter()
    size = prompt_size(prompt)
    try:
        result = invoke()
    except Exception as exc:
        record(
            "llm_call",
            stage=stage,
            outcome="error",
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
            prompt_characters=size,
            error_type=type(exc).__name__,
        )
        raise
    record(
        "llm_call",
        stage=stage,
        outcome="success",
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
        prompt_characters=size,
    )
    return result


def snapshot() -> dict[str, int]:
    """Return process-local counters for a lightweight health dashboard."""
    with _lock:
        return dict(_counts)
