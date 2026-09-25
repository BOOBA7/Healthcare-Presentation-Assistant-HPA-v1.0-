"""Deterministic claim/evidence validation and human semantic review."""

from copy import deepcopy

from app.application.validators.evidence_provenance_validator import EvidenceProvenanceValidator
from app.domain.exceptions.validation_error import ValidationError
from app.domain.models.claim_evidence import EvidenceLink, MedicalClaim
from app.domain.models.slide import Slide


class ClaimEvidenceService:
    @staticmethod
    def set_claims(slide: Slide, claims: list[MedicalClaim]) -> None:
        existing = {claim.id: claim for claim in slide.claims}
        for claim in claims:
            previous = existing.get(claim.id)
            if previous and claim.text != previous.text and claim.revision <= previous.revision:
                raise ValidationError("A changed claim must use a newer revision.")
        changed = {
            claim.id for claim in claims
            if claim.id in existing and claim.model_dump() != existing[claim.id].model_dump()
        }
        slide.claims = deepcopy(claims)
        for link in slide.evidence_links:
            if link.claim_id in changed:
                link.semantic_review = "pending"
                link.semantic_reviewed_by = None
                link.provenance_verified = False
        ClaimEvidenceService._refresh(slide)

    @staticmethod
    def review_link(slide: Slide, link: EvidenceLink, resources, actor: str) -> None:
        claims = {claim.id: claim for claim in slide.claims}
        claim = claims.get(link.claim_id)
        if claim is None or claim.revision != link.claim_revision:
            raise ValidationError("The evidence link targets an unknown or obsolete claim revision.")
        ClaimEvidenceService.verify_provenance(link, resources)
        link.provenance_verified = True
        link.semantic_reviewed_by = actor if link.semantic_review != "pending" else None
        replaced = False
        for index, previous in enumerate(slide.evidence_links):
            if previous.id == link.id:
                if link.revision <= previous.revision:
                    raise ValidationError("The evidence link revision is stale.")
                slide.evidence_links[index] = link
                replaced = True
                break
        if not replaced:
            slide.evidence_links.append(link)
        ClaimEvidenceService._refresh(slide)

    @staticmethod
    def verify_provenance(link: EvidenceLink, resources) -> None:
        """Verify only source identity/location/passage, never relevance."""
        resource = next((item for item in resources if item.id == link.resource_id), None)
        if resource is None:
            raise ValidationError("The evidence link cites an unknown resource ID.")
        expected_title = resource.title or resource.filename
        if link.resource_title != expected_title:
            raise ValidationError("The evidence link title does not match the stored resource title.")
        expected_kind = "slide" if resource.file_type.value == "pptx" else "page"
        if link.location_kind != expected_kind:
            raise ValidationError("The evidence link uses the wrong source location type.")
        page_text = next((page.get("text") for page in resource.extracted_pages
                          if page.get("page") == link.location_number), None)
        if not isinstance(page_text, str):
            raise ValidationError("The evidence link cites a source location that does not exist.")
        if EvidenceProvenanceValidator._normalize(link.exact_passage) not in EvidenceProvenanceValidator._normalize(page_text):
            raise ValidationError("The evidence link passage was not found at the cited source location.")
        # DOI/URL are retained only if actually present in the supplied source.
        searchable = EvidenceProvenanceValidator._normalize(page_text + " " + (resource.extracted_text or ""))
        for label, supplied in (("DOI", link.doi), ("URL", link.url)):
            if supplied and EvidenceProvenanceValidator._normalize(supplied) not in searchable:
                raise ValidationError(f"The evidence link {label} is not attributable to the supplied resource.")

    @staticmethod
    def _refresh(slide: Slide) -> None:
        current = {(claim.id, claim.revision) for claim in slide.claims}
        approved = [link for link in slide.evidence_links
                    if (link.claim_id, link.claim_revision) in current
                    and link.provenance_verified and link.semantic_review == "approved"]
        supported = {link.claim_id for link in approved}
        slide.evidence_verified = bool(slide.claims) and supported == {claim.id for claim in slide.claims}
        slide.evidence_review_required = not slide.evidence_verified or bool(slide.legacy_references)
        if slide.content_origin != "ai_generated" and slide.content_classification == "medical":
            slide.source_missing = not slide.evidence_verified
            slide.authorship_warning = (
                "user-provided, source missing" if slide.source_missing else None
            )
