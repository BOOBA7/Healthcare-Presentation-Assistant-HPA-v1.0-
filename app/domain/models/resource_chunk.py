"""A normalized, persisted PDF passage used by local retrieval."""

from pydantic import BaseModel, Field


class ResourceChunk(BaseModel):
    """One deterministic chunk extracted from one user-provided PDF page."""

    resource_id: str
    page: int = Field(ge=1)
    position: int = Field(ge=0)
    text: str = Field(min_length=1)
    title: str
