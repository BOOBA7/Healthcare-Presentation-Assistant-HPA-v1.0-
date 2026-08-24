"""Explicit human declaration used to resolve a professional-scope mismatch."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ProfessionalScopeDeclaration(BaseModel):
    """Structured human input that the model is not allowed to infer."""

    declared_role: str = Field(min_length=3, max_length=200)
    delivery_purpose: str = Field(min_length=12, max_length=1_000)
    confirmed_within_scope: bool
    declared_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
