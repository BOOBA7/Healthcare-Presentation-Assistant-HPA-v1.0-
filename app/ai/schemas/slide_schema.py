from typing import List

from pydantic import BaseModel, Field


class SlideReferenceSchema(BaseModel):
    """
    Scientific reference associated with a slide.
    """

    title: str = Field(
        ...,
        description="Scientific publication or guideline title.",
    )

    source: str = Field(
        ...,
        description="Journal, organization or conference.",
    )

    year: int | None = Field(
        default=None,
        description="Publication year.",
    )


class SlideSchema(BaseModel):
    """
    Structured output expected from the LLM
    for generating a single presentation slide.
    """

    slide_number: int = Field(
        ...,
        ge=1,
        description="Slide order in the presentation.",
    )

    title: str = Field(
        ...,
        description="Slide title.",
    )

    objective: str = Field(
        ...,
        description="Learning objective of the slide.",
    )

    key_messages: List[str] = Field(
        default_factory=list,
        description="Main scientific messages to communicate.",
    )

    content: str = Field(
        ...,
        description="Scientific content that will appear on the slide.",
    )

    speaker_notes: str = Field(
        ...,
        description="Detailed presenter notes not displayed on the slide.",
    )

    references: List[SlideReferenceSchema] = Field(
        default_factory=list,
        description="Scientific references supporting the slide.",
    )

    visual_recommendations: List[str] = Field(
        default_factory=list,
        description="Recommended figures, diagrams, icons or charts.",
    )
