"""Non-authoritative source comparison and explicit planning-transfer records."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class DiscussionPosition(BaseModel):
    id: str
    resource_id: str
    resource_title: str
    scientific_date: str | None = None
    location_kind: Literal["page", "slide"]
    location_number: int = Field(ge=1)
    section: str | None = None
    exact_passage: str = Field(min_length=12)
    doi: str | None = None
    url: str | None = None
    uncertainty: str
    human_review_required: bool = True


class DiscussionComparison(BaseModel):
    """A view derived from current chat citations, never a scientific judgement."""

    version: str = "discussion-conflict-v1"
    classification: Literal["different_passages", "potential_conflict", "deterministic_conflict"]
    rule: str
    positions: list[DiscussionPosition]
    human_review_required: bool = True


class PlanningTransfer(BaseModel):
    """Human-approved input for later planning; applying it is outside phase 06.3."""

    version: str = "discussion-transfer-v1"
    revision: int = Field(default=1, ge=1)
    destination: Literal["agenda", "blueprint"]
    content: str = Field(min_length=1, max_length=20_000)
    retained_position_ids: list[str] = Field(min_length=1)
    uncertainties: list[str] = Field(default_factory=list)
    positions: list[DiscussionPosition] = Field(min_length=1)
    discussion_digest: str
    context_digest: str
    coverage_digest: str
    resources_digest: str
    passages_digest: str
    approved_by: str
    approved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["approved", "obsolete"] = "approved"
