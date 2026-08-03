from datetime import datetime

from pydantic import BaseModel, Field


class GenerationRecord(BaseModel):
    """Reproducibility metadata captured for an LLM generation action."""

    stage: str
    model_name: str
    prompt_version: str
    retrieval_version: str
    retrieval_mode: str = "bm25"
    harness_version: str = "legacy-unknown"
    workflow_version: str = "legacy-unknown"
    created_at: datetime = Field(default_factory=datetime.now)
