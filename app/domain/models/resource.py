from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from app.domain.enums.resource_type import ResourceType
from app.domain.enums.language import Language


class Resource(BaseModel):
    """
    Represents a scientific resource uploaded by the user.

    A resource may be a PDF, DOCX, PPTX or any scientific
    document used as evidence for presentation generation.
    """

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
        description="Extracted PDF pages with page number and text for evidence provenance.",
    )

    is_validated: bool = Field(
        default=False,
        description="Indicates whether the PDF was successfully parsed into usable text. Human production approval is held in PresentationState.",
    )

    uploaded_at: datetime = Field(
        default_factory=datetime.now,
        description="Upload timestamp.",
    )
