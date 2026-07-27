from datetime import datetime

from pydantic import BaseModel, Field


class ResourceAnalysis(BaseModel):
    """Brief AI overview of the user-uploaded evidence set."""

    summary: str = Field(min_length=1)
    resource_ids: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)
