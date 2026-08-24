"""Provider-accurate, UTC generation metadata shared by every LLM use case."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.versioning import HARNESS_VERSION, PROMPT_VERSION, RETRIEVAL_VERSION, WORKFLOW_VERSION
from app.domain.models.generation_record import GenerationRecord
from app.domain.models.presentation import Presentation


def append_generation_record(presentation: Presentation, stage: str) -> None:
    """Append reproducibility metadata for one configured-model generation."""
    settings = get_settings()
    presentation.generation_records.append(
        GenerationRecord(
            stage=stage,
            provider=settings.configured_llm_provider,
            model_name=settings.configured_llm_model,
            prompt_version=PROMPT_VERSION,
            retrieval_version=RETRIEVAL_VERSION,
            retrieval_mode=presentation.evidence_context_mode.value,
            harness_version=HARNESS_VERSION,
            workflow_version=WORKFLOW_VERSION,
        )
    )
    presentation.updated_at = datetime.now(UTC)
