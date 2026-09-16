from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, PrivateAttr, model_validator
from app.domain.models.source_metadata import SourceMetadata
from app.domain.enums.resource_type import ResourceType
from app.domain.enums.language import Language


class Resource(BaseModel):
    """
    Represents a scientific resource uploaded by the user.

    Supported originals are PDF, PNG/JPEG and restricted PPTX evidence.
    Legacy enum values do not authorise other input formats.
    """

    metadata: SourceMetadata = Field(default_factory=SourceMetadata)
    # Never serialized into Project JSON, telemetry, API payloads or model prompts.
    _original_content: bytes | None = PrivateAttr(default=None)
    _ocr_review_receipt: str | None = PrivateAttr(default=None)

    @model_validator(mode="before")
    @classmethod
    def migrate_metadata(cls, value):
        """Upgrade old JSON in memory without inventing provenance or page numbers."""
        if isinstance(value, dict) and "metadata" not in value:
            value = dict(value)
            value["metadata"] = {
                "media_type": "application/pdf" if value.get("file_type") == "pdf" else None,
                "locations": [
                    {"kind": "page", "number": page["page"]}
                    for page in value.get("extracted_pages", [])
                    if type(page.get("page")) is int and page["page"] > 0
                ],
            }
        return value

    id: str = Field(
        ...,
        description="Unique resource identifier.",
    )

    filename: str = Field(
        ...,
        description="Original filename.",
    )

    title: Optional[str] = Field(
        default=None,
        description="Document title extracted from the resource.",
    )

    source: Optional[str] = Field(
        default=None,
        description="Publisher or source of the document.",
    )


    language: Language = Language.ENGLISH
    file_type: ResourceType = Field(
        ...,
        description="Document type (pdf, docx, pptx, txt...).",
    )

    path: str | None = Field(
        default=None,
        description="Local path or object-storage key for the resource.",
    )

    extracted_text: Optional[str] = Field(
        default=None,
        description="Text extracted from the document.",
    )

    extracted_pages: list[dict[str, object]] = Field(
        default_factory=list,
        description="Extracted source pages or PPTX slides; page holds the original 1-based location.",
    )

    is_validated: bool = Field(
        default=False,
        description="Indicates whether the PDF was successfully parsed into usable text. Human production approval is held in PresentationState.",
    )

    uploaded_at: datetime = Field(
        default_factory=datetime.now,
        description="Upload timestamp.",
    )
