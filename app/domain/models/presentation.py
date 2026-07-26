from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.domain.enums.presentation_status import PresentationStatus
from app.domain.models.blueprint import Blueprint
from app.domain.models.agenda import Agenda
from app.domain.enums.presentation_theme import PresentationTheme
from app.domain.models.presentation_state import PresentationState
from app.domain.models.resource import Resource
from app.domain.models.slide import Slide
from app.domain.models.user_profile import UserProfile
from app.domain.value_objects.presentation_context import PresentationContext


class Presentation(BaseModel):
    """
    Represents a healthcare presentation project.

    This is the Aggregate Root of the domain.
    It owns the workflow state, resources,
    blueprint and generated slides.
    """

    id: str = Field(
        ...,
        description="Unique presentation identifier.",
    )

    title: str = Field(
        ...,
        description="Presentation title.",
    )

    context: PresentationContext = Field(
        ...,
        description="Presentation context.",
    )

    state: PresentationState = Field(
        ...,
        description="Current workflow state.",
    )

    status: PresentationStatus = Field(
        default=PresentationStatus.DRAFT,
        description="Current presentation lifecycle status.",
    )

    resources: List[Resource] = Field(
        default_factory=list,
        description="Scientific resources attached to the presentation.",
    )

    blueprint: Optional[Blueprint] = Field(
        default=None,
        description="Validated presentation blueprint.",
    )

    slides: List[Slide] = Field(
        default_factory=list,
        description="Generated presentation slides.",
    )

    agenda: Agenda | None = Field(
        default=None,
        description="Model-proposed agenda reviewed by the user and exported as slide 2.",
    )

    theme: PresentationTheme = Field(
        default=PresentationTheme.CLINICAL,
        description="Professional PowerPoint visual theme selected by the user.",
    )

    custom_template_id: str | None = Field(
        default=None,
        description="Optional user-owned PPTX template used as the export base.",
    )

    owner_profile: UserProfile = Field(
        default_factory=UserProfile,
        description="Professional profile snapshot used for deterministic content adaptation.",
    )

    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Presentation creation timestamp.",
    )

    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="Last modification timestamp.",
    )
