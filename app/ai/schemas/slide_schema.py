from typing import List, Literal

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

    resource_id: str | None = Field(default=None, description="Validated source resource ID.")

    page: int | None = Field(default=None, ge=1, description="Supporting PDF page number.")

    location_kind: Literal["page", "slide"] = Field(
        default="page", description="Use slide only for a supplied PowerPoint source."
    )

    evidence_excerpt: str | None = Field(default=None, description="Short supporting excerpt from the source.")

    claim_id: str = Field(description="Stable ID of exactly one claim supported by this passage.")

    claim_text: str = Field(description="Exact claim text supported by this passage.")

    section: str | None = Field(default=None, description="Source section, only when supplied.")

    doi: str | None = Field(default=None, description="DOI, only when present in the supplied source.")

    url: str | None = Field(default=None, description="Link, only when present in the supplied source.")

    claim_value: str | None = Field(default=None, description="Exact supplied value, or null when absent.")

    claim_unit: str | None = Field(default=None, description="Exact supplied unit, or null when absent.")

    claim_uncertainty: str | None = Field(default=None, description="Missingness or uncertainty stated by the source.")

    missing_value: bool = Field(default=False, description="True only when the source does not provide a value.")

    conflict_group_id: str | None = Field(default=None, description="Shared ID for source positions that conflict.")

    source_position: str | None = Field(default=None, description="Neutral label for this source position.")


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

    speaker_note_references: List[SlideReferenceSchema] = Field(
        default_factory=list,
        description="Evidence supporting claims made only in the speaker notes.",
    )

    references: List[SlideReferenceSchema] = Field(
        default_factory=list,
        description="Scientific references supporting the slide.",
    )

    visual_recommendations: List[str] = Field(
        default_factory=list,
        description="Recommended figures, diagrams, icons or charts.",
    )
