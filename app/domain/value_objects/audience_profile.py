from typing import List

from pydantic import BaseModel

from app.domain.enums.audience_type import AudienceType


class AudienceProfile(BaseModel):
    audience_type: AudienceType

    knowledge_level: str

    explanation_level: str

    statistics_level: str

    terminology_level: str

    preferred_visuals: List[str]

    learning_focus: str

    interaction_style: str

    presenter_expectations: List[str]
