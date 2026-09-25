from datetime import datetime
from typing import List, Literal, Optional

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.models.claim_evidence import EvidenceLink, LegacySlideReference, MedicalClaim
from app.domain.value_objects.speaker_note import SpeakerNote


class SlideVisual(BaseModel):
    """A user-selected visual; no field can request generated imagery."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    kind: Literal["image", "table", "bar_chart", "line_chart", "diagram"]
    resource_id: str | None = Field(default=None, min_length=1, max_length=128)
    asset_id: str | None = Field(default=None, min_length=1, max_length=256)
    title: str = Field(default="", max_length=500)
    columns: list[str] = Field(default_factory=list, max_length=12)
    rows: list[list[str]] = Field(default_factory=list, max_length=20)
    categories: list[str] = Field(default_factory=list, max_length=20)
    series: dict[str, list[float]] = Field(default_factory=dict)
    nodes: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def supplied_content_only(self):
        if self.kind == "image":
            if not self.resource_id or not self.asset_id:
                raise ValueError("A supplied image must identify its Project resource and reviewed asset.")
            if self.columns or self.rows or self.categories or self.series or self.nodes:
                raise ValueError("An image placement cannot contain generated values.")
        elif self.resource_id or self.asset_id:
            raise ValueError("Only supplied-image placements may reference an asset.")
        elif self.kind == "table":
            if not self.columns or not self.rows or any(len(row) != len(self.columns) for row in self.rows):
                raise ValueError("A table requires supplied columns and complete supplied rows.")
        elif self.kind in {"bar_chart", "line_chart"}:
            if not self.categories or not self.series or any(len(values) != len(self.categories) for values in self.series.values()):
                raise ValueError("A chart requires supplied categories and one value per category.")
        elif not self.nodes:
            raise ValueError("A diagram requires supplied node labels.")
        return self


class Slide(BaseModel):
    """
    Represents a single slide of a healthcare presentation.
    """

    slide_number: int = Field(
        ...,
        gt=0,
        description="Slide position in the presentation.",
    )

    title: str = Field(
        ...,
        description="Slide title.",
    )

    objective: Optional[str] = Field(
        default=None,
        description="Learning objective of the slide.",
    )

    key_messages: List[str] = Field(
        default_factory=list,
        description="Main messages to communicate.",
    )

    content: str = Field(
        default="",
        description="Generated slide content.",
    )

    speaker_notes: Optional[str] = Field(
        default=None,
        description="Speaker notes associated with the slide.",
    )

    speaker_note: SpeakerNote | None = Field(
        default=None,
        description="Speaker notes and their evidence, separate from visible slide content.",
    )

    references: List[str] = Field(
        default_factory=list,
        description="Scientific references supporting the slide.",
    )

    reference_details: List[dict[str, object]] = Field(
        default_factory=list,
        description="Evidence provenance: resource ID, page, excerpt and bibliographic reference.",
    )

    claims: List[MedicalClaim] = Field(default_factory=list)

    evidence_links: List[EvidenceLink] = Field(default_factory=list)

    legacy_references: List[LegacySlideReference] = Field(default_factory=list)

    evidence_verified: bool = Field(
        default=False,
        description="Whether every citation was verified against an uploaded PDF page.",
    )

    visual_recommendations: List[str] = Field(
        default_factory=list,
        description="Suggested visuals for this slide.",
    )

    layout: Literal["text_only", "text_left_visual_right", "visual_left_text_right", "visual_focus"] = "text_only"

    visual: SlideVisual | None = Field(
        default=None,
        description="User-supplied image or deterministic visual built only from user-supplied values.",
    )

    is_validated: bool = Field(
        default=False,
        description="Whether the slide has been validated by the user.",
    )

    approved_by: str | None = Field(default=None, max_length=256)

    approved_at: datetime | None = None

    reviewer_comments: str | None = Field(
        default=None,
        description="Human reviewer comments for this slide.",
    )

    content_origin: Literal["ai_generated", "user_edited", "user_authored"] = Field(
        default="ai_generated",
        description="Whether this slide was generated by the model or written/edited by the user.",
    )

    content_classification: Literal["medical", "nonmedical"] = Field(
        default="medical",
        description="Human-declared classification used by the deterministic evidence gate.",
    )

    source_missing: bool = Field(
        default=False,
        description="True for user-provided medical text that has no reviewed claim evidence.",
    )

    authorship_warning: str | None = Field(
        default=None,
        description="Explicit warning attached to an unsupported user-provided medical draft.",
    )

    original_ai_snapshot: dict[str, object] | None = Field(
        default=None,
        description="Original model content retained when a user first edits an AI slide.",
    )

    evidence_review_required: bool = Field(
        default=False,
        description="True when manual content changes mean evidence can no longer be attributed to the model output.",
    )
    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_references(cls, value):
        """Keep old slide citations losslessly, idempotently and unassigned.

        A slide-level reference cannot be attributed to every claim.  Migration
        therefore creates review items only; it grants no semantic approval.
        """
        if (not isinstance(value, dict) or value.get("legacy_references")
                or value.get("claims") or value.get("evidence_links")):
            return value
        references = value.get("reference_details")
        if not isinstance(references, list) or not references:
            return value
        migrated = dict(value)
        legacy = []
        for reference in references:
            if not isinstance(reference, dict):
                continue
            canonical = json.dumps(reference, sort_keys=True, separators=(",", ":"), default=str)
            legacy.append({
                "migration_id": f"legacy-{hashlib.sha256(canonical.encode()).hexdigest()[:20]}",
                "reference": reference,
                "review_required": True,
            })
        migrated["legacy_references"] = legacy
        migrated["evidence_review_required"] = True
        migrated["evidence_verified"] = False
        return migrated
