"""Persisted, deterministic evidence-coverage decisions for presentation planning."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


CoverageDimension = Literal["topic", "objective", "audience", "depth", "slide_count"]


class CoveragePassage(BaseModel):
    """A real persisted passage which deterministically matched one dimension."""

    resource_id: str
    resource_title: str
    location_kind: Literal["page", "slide"]
    location_number: int = Field(ge=1)
    passage_position: int = Field(ge=0)
    matched_terms: list[str] = Field(default_factory=list)


class CoverageResult(BaseModel):
    """One independently reviewable workflow decision."""

    dimension: CoverageDimension
    label: str
    sufficient: bool
    reason: str
    requested_resource: str | None = None
    passages: list[CoveragePassage] = Field(default_factory=list)
    human_review_required: bool = True


class EvidenceCoverageAssessment(BaseModel):
    """Server-created decision; it is not a scientific-validity judgement."""

    version: str = "coverage-v1"
    context_digest: str
    resources_digest: str
    passages_digest: str
    results: list[CoverageResult]
    sufficient: bool
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scientific_validity_reviewed: bool = False

