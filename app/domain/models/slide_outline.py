from pydantic import BaseModel, Field


class SlideOutline(BaseModel):
    """
    Represents a planned slide before
    its content is generated.
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

    key_message: str = Field(
        ...,
        description="Main message the audience should remember.",
    )
