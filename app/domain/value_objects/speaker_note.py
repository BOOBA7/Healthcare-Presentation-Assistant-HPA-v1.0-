"""Speaker notes kept separate from visible slide content and its evidence."""

from pydantic import BaseModel, Field

from app.domain.models.claim_evidence import EvidenceLink, MedicalClaim


class SpeakerNote(BaseModel):
    text: str = Field(min_length=1, max_length=40_000)
    claims: list[MedicalClaim] = Field(default_factory=list)
    evidence_links: list[EvidenceLink] = Field(default_factory=list)
    is_approved: bool = False
    approved_by: str | None = Field(default=None, max_length=256)
