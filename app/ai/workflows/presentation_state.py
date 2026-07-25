from pydantic import BaseModel, Field


class PresentationState(BaseModel):
    topic: str | None = None
    audience: str | None = None
    presentation_type: str | None = None
    language: str | None = None
    duration_minutes: int | None = None
    objective: str | None = None
    blueprint: list[str] = Field(default_factory=list)
    slides: list[dict] = Field(default_factory=list)
