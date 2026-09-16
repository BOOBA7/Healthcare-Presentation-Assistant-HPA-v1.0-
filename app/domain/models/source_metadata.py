"""Versioned source descriptors with traceable scientific-date evidence."""

from typing import Literal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["page", "slide", "region"]
    number: int = Field(gt=0, strict=True)
    region: tuple[float, float, float, float] | None = None


class OcrRegion(BaseModel):
    """A line in original-page normalized top-left coordinates, before correction."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    page: int = Field(default=1, gt=0, strict=True)
    box: tuple[float, float, float, float]
    text: str = Field(min_length=1, max_length=10000)
    confidence: float = Field(ge=0, le=1)
    # No confirmation may be supplied or fabricated in 04.2.
    uncertain: Literal[True] = True

    @model_validator(mode="after")
    def valid_box(self):
        x0, y0, x1, y1 = self.box
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError("Invalid original-region coordinates")
        return self


class OcrReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch: int = Field(gt=0, strict=True)
    region_index: int = Field(ge=0, strict=True)
    original_value: str = Field(min_length=1, max_length=10000)
    corrected_value: str = Field(min_length=1, max_length=10000)
    actor: str = Field(min_length=1)
    confirmed_at: datetime
    original_sha256: str
    provenance: Literal["user_confirmed"] = "user_confirmed"

    @model_validator(mode="after")
    def aware_timestamp(self):
        if self.confirmed_at.tzinfo is None:
            raise ValueError("Review timestamp must be timezone-aware")
        return self


class SourceAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["image", "table"]
    media_type: str | None = None
    location: SourceLocation
    caption: str | None = None
    provenance: str | None = None
    rights: str | None = None


class SourceDateEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    precision: Literal["year", "month", "day"]
    kind: Literal["publication", "update"]
    origin: Literal["document_text", "scientific_metadata", "ocr_text", "user_confirmed"]
    page: int | None = Field(default=None, gt=0)
    excerpt: str
    metadata_key: str | None = None


class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    origin: Literal["legacy", "pdf_memory_import", "raster_memory_import"] = "legacy"
    media_type: str | None = None
    author: str | None = None
    organisation: str | None = None
    publisher: str | None = None
    rights: str | None = None
    provenance: str | None = None
    locations: list[SourceLocation] = Field(default_factory=list)
    assets: list[SourceAsset] = Field(default_factory=list)
    extensions: dict[str, str] = Field(default_factory=dict)
    original_sha256: str | None = None
    original_size: int | None = Field(default=None, ge=0)
    pdf_metadata: dict[str, str] = Field(default_factory=dict)
    xml_metadata: str | None = None
    scientific_date: SourceDateEvidence | None = None

    ocr_engine: str | None = None
    ocr_regions: list[OcrRegion] = Field(default_factory=list)
    image_metadata: dict[str, str] = Field(default_factory=dict)
    ocr_reviews: list[OcrReview] = Field(default_factory=list)
