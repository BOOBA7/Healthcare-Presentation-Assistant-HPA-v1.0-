from pydantic import BaseModel, Field


class AgendaSchema(BaseModel):
    """Structured high-level sections proposed before Blueprint generation."""

    sections: list[str] = Field(min_length=1, max_length=12)
