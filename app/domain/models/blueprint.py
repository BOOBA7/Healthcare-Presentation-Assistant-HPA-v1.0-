from typing import List, Optional

from pydantic import BaseModel, Field

from app.domain.models.slide_outline import SlideOutline


class Blueprint(BaseModel):
    """
    Represents the validated blueprint of a healthcare presentation.

    The blueprint defines the presentation structure before
    generating the final slides.
    """

    title: str = Field(
        ...,
        description="Blueprint title.",
    )

    learning_objective: str = Field(
        ...,
        description="Overall learning objective.",
    )

    target_number_of_slides: int = Field(
        ...,
        gt=0,
        description="Expected number of slides.",
    )

    storytelling: str = Field(
        ...,
        description="Narrative strategy.",
    )

    sections: List[str] = Field(
        default_factory=list,
        description="Presentation sections.",
    )

    slides: List[SlideOutline] = Field(
        default_factory=list,
        description="Blueprint slide outlines.",
    )

    is_validated: bool = Field(
        default=False,
        description="Whether the blueprint has been validated.",
    )

    reviewer_comments: Optional[str] = Field(
        default=None,
        description="Reviewer comments.",
    )
