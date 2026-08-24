"""Structured, recoverable reason why one slide could not be generated."""

from typing import Literal

from pydantic import BaseModel, Field


class SlideGenerationBlocker(BaseModel):
    """A deterministic blocker scoped to one blueprint item.

    The payload intentionally contains retrieval metadata only. It never stores
    PDF page text in the workflow state or audit trail.
    """

    slide_number: int = Field(..., gt=0)
    code: Literal["INSUFFICIENT_EVIDENCE", "INVALID_AI_PROVENANCE"]
    message: str = Field(min_length=1)
    diagnostic: dict[str, object] = Field(default_factory=dict)

