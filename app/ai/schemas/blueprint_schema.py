from typing import List

from pydantic import BaseModel, Field


class SlideOutline(BaseModel):
    """
    Represents a generated slide outline
    returned by the AI blueprint generation step.
    """

    slide_number: int = Field(
        ...,
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

    key_message: str = Field(
        ...,
        description="Main message the audience should remember.",
    )

    key_message: str = Field(
        ...,
        description="Main message the audience should remember.",
    )


class BlueprintSchema(BaseModel):
    """
    Structured output expected from the LLM
    when generating a presentation blueprint.
    """

    title: str = Field(
        ...,
        description="Presentation title.",
    )

    storytelling: str = Field(
        ...,
        description="Scientific storytelling strategy.",
    )

    learning_objectives: List[str] = Field(
        ...,
        description="Main learning objectives.",
    )

    estimated_duration: int = Field(
        ...,
        description="Estimated presentation duration in minutes.",
    )

    slides: List[SlideOutline] = Field(
        ...,
        description="Ordered presentation slides.",
    )

    key_message: str = Field(
        ...,
        description="Main message the audience should remember.",
    )
