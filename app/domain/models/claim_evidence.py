"""Stable claim-level evidence records.

Provenance verification is deterministic.  Semantic relevance and scientific
validity remain separate human judgements.
"""

from typing import Literal

from pydantic import BaseModel, Field


class MedicalClaim(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    revision: int = Field(default=1, ge=1)
    text: str = Field(min_length=1, max_length=20_000)
    value: str | None = Field(default=None, max_length=500)
    unit: str | None = Field(default=None, max_length=100)
    uncertainty: str | None = Field(default=None, max_length=1_000)


class EvidenceLink(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    revision: int = Field(default=1, ge=1)
    claim_id: str = Field(min_length=1, max_length=128)
    claim_revision: int = Field(ge=1)
    resource_id: str = Field(min_length=1, max_length=128)
    resource_title: str = Field(min_length=1, max_length=1_000)
    location_kind: Literal["page", "slide"]
    location_number: int = Field(ge=1)
    section: str | None = Field(default=None, max_length=1_000)
    exact_passage: str = Field(min_length=12, max_length=20_000)
    doi: str | None = Field(default=None, max_length=1_000)
    url: str | None = Field(default=None, max_length=2_000)
    provenance_verified: bool = False
    semantic_review: Literal["pending", "approved", "rejected"] = "pending"
    semantic_reviewed_by: str | None = Field(default=None, max_length=256)


class LegacySlideReference(BaseModel):
    """Lossless, unassigned migration of a pre-06.1 slide reference."""

    migration_id: str
    reference: dict[str, object]
    review_required: bool = True

