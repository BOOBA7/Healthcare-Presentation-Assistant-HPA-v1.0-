"""Versioned source descriptors with traceable scientific-date evidence."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["page", "slide", "region"]
    number: int = Field(gt=0, strict=True)
    region: tuple[float, float, float, float] | None = None


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
    origin: Literal["document_text", "scientific_metadata"]
    page: int | None = Field(default=None, gt=0)
    excerpt: str
    metadata_key: str | None = None


class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    origin: Literal["legacy", "pdf_memory_import"] = "legacy"
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
