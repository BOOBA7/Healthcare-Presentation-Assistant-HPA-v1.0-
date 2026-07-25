from typing import List, Optional

from pydantic import BaseModel, Field


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

    references: List[str] = Field(
        default_factory=list,
        description="Scientific references supporting the slide.",
    )

    visual_recommendations: List[str] = Field(
        default_factory=list,
        description="Suggested visuals for this slide.",
    )

    is_validated: bool = Field(
        default=False,
        description="Whether the slide has been validated by the user.",
    )
