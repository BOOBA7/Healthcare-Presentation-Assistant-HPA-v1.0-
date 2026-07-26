from pydantic import BaseModel, Field


class Agenda(BaseModel):
    """Human-reviewed agenda displayed as slide 2 of every exported deck."""

    items: list[str] = Field(default_factory=list, min_length=1)
    is_validated: bool = False
    reviewer_comments: str | None = None
