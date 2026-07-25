from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.domain.enums.language import Language
from app.domain.enums.resource_type import ResourceType


class Resource(BaseModel):
    """
    Represents a scientific resource uploaded by the user.
    """

    id: str = Field(
        ...,
        description="Unique resource identifier.",
    )

    filename: str = Field(
        ...,
        description="Original filename.",
    )

    file_type: ResourceType = Field(
        ...,
        description="Scientific resource type.",
    )

    title: Optional[str] = Field(
        default=None,
        description="Extracted document title.",
    )

    publisher: Optional[str] = Field(
        default=None,
        description="Publisher or organization.",
    )

    language: Language = Field(
        default=Language.ENGLISH,
        description="Document language.",
    )

    extracted_text: Optional[str] = Field(
        default=None,
        description="Extracted document content.",
    )

    is_validated: bool = Field(
        default=False,
        description="Whether the user validated this resource.",
    )

    uploaded_at: datetime = Field(
        default_factory=datetime.now,
        description="Upload timestamp.",
    )
