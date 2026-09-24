from typing import Literal

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

    slide_role: Literal["title", "agenda", "content", "conclusion", "references", "thank_you"] = Field(
        ...,
        description="Structural role of the slide in the complete deck.",
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

    supporting_source_ids: list[str] = Field(
        default_factory=list,
        description="Validated Project resource IDs; may be empty only for non-assertive structural slides.",
    )

    planned_visual: str = Field(
        ...,
        description="Specific visual planned for the slide, or an explicit statement that none is needed.",
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

    learning_objectives: list[str] = Field(
        ...,
        description="Main learning objectives.",
    )

    estimated_duration: int = Field(
        ...,
        description="Estimated presentation duration in minutes.",
    )

    slides: list[SlideOutline] = Field(
        ...,
        description="Ordered presentation slides.",
    )

    key_message: str = Field(
        ...,
        description="Main message the audience should remember.",
    )
