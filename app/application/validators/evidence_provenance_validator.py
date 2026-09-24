"""Deterministic checks for evidence citations produced by the language model."""

import unicodedata
from app.application.services.pptx_roles import label_pptx_reference, source_warning

from app.domain.models.resource import Resource
from app.domain.models.slide import Slide
from app.domain.models.claim_evidence import EvidenceLink
from app.domain.exceptions.validation_error import ValidationError


class EvidenceProvenanceValidator:
    """Accept a citation only when it points to an exact uploaded PDF passage."""

    def validate_slide(
        self,
        slide: Slide,
        resources: list[Resource],
        *,
        require_claims: bool = False,
    ) -> None:
        if not slide.claims and not require_claims:
            if not slide.reference_details:
                raise ValidationError(f"Slide {slide.slide_number} has no evidence citation.")
            resources_by_id = {resource.id: resource for resource in resources}
            for reference in slide.reference_details:
                self._validate_reference(slide.slide_number, reference, resources_by_id)
            slide.evidence_verified = False
            slide.evidence_review_required = True
            return
        self._validate_claim_set(slide.slide_number, slide.claims, slide.evidence_links, resources, "slide")
        if slide.speaker_notes:
            if slide.speaker_note is None or slide.speaker_note.text != slide.speaker_notes:
                raise ValidationError(f"Slide {slide.slide_number} speaker notes have no separate evidence record.")
            self._validate_claim_set(
                slide.slide_number,
                slide.speaker_note.claims,
                slide.speaker_note.evidence_links,
                resources,
                "speaker notes",
            )
            slide.speaker_note.is_approved = False
            slide.speaker_note.approved_by = None

        resources_by_id = {resource.id: resource for resource in resources}
        if any(source_warning(resources_by_id[link.resource_id]) for link in slide.evidence_links):
            slide.references = [link.resource_title for link in slide.evidence_links]
        # Provenance is verified now; scientific relevance remains a separate
        # human decision and cannot be granted by generation.
        slide.evidence_verified = False
        slide.evidence_review_required = True

    def _validate_claim_set(self, slide_number, claims, links, resources, label: str) -> None:
        from app.application.services.claim_evidence import ClaimEvidenceService

        if not claims:
            raise ValidationError(f"Slide {slide_number} {label} have no traceable claims.")
        claim_by_id = {claim.id: claim for claim in claims}
        if len(claim_by_id) != len(claims):
            raise ValidationError(f"Slide {slide_number} {label} reuse a claim ID.")
        linked: dict[str, list[EvidenceLink]] = {claim.id: [] for claim in claims}
        for link in links:
            claim = claim_by_id.get(link.claim_id)
            if claim is None or link.claim_revision != claim.revision:
                raise ValidationError(f"Slide {slide_number} {label} cite an unknown claim revision.")
            ClaimEvidenceService.verify_provenance(link, resources)
            link.provenance_verified = True
            linked[claim.id].append(link)
        if any(not evidence for evidence in linked.values()):
            raise ValidationError(f"Slide {slide_number} {label} contain a claim without exact evidence.")

        for claim in claims:
            passages = " ".join(link.exact_passage for link in linked[claim.id])
            normalized_passages = self._normalize(passages)
            if claim.missing_value:
                if claim.value is not None or claim.unit is not None or not claim.uncertainty:
                    raise ValidationError(
                        f"Slide {slide_number} {label} silently complete a missing value."
                    )
            else:
                for field_name, value in (("value", claim.value), ("unit", claim.unit)):
                    if value and self._normalize(value) not in normalized_passages:
                        raise ValidationError(
                            f"Slide {slide_number} {label} {field_name} is absent from its exact evidence."
                        )

        conflict_groups: dict[str, list] = {}
        for claim in claims:
            if claim.conflict_group_id:
                conflict_groups.setdefault(claim.conflict_group_id, []).append(claim)
        for group_id, positions in conflict_groups.items():
            if len(positions) < 2 or any(not claim.source_position for claim in positions):
                raise ValidationError(
                    f"Slide {slide_number} {label} hide a source conflict in group {group_id}."
                )
        same_assertion: dict[str, list] = {}
        for claim in claims:
            same_assertion.setdefault(self._normalize(claim.text), []).append(claim)
        for positions in same_assertion.values():
            supplied_values = {self._normalize(claim.value) for claim in positions if claim.value}
            if len(supplied_values) > 1:
                group_ids = {claim.conflict_group_id for claim in positions}
                if len(group_ids) != 1 or None in group_ids:
                    raise ValidationError(
                        f"Slide {slide_number} {label} silently merge conflicting supplied values."
                    )

    def validate_presentation(self, slides: list[Slide], resources: list[Resource]) -> None:
        for slide in slides:
            if slide.content_origin == "ai_generated":
                # Existing pre-08 snapshots retain their lossless slide-level
                # citations. Generation now requires claim-level records, but
                # reopening/exporting an already approved legacy Project must
                # not destroy it.
                if slide.claims:
                    self.validate_slide(slide, resources, require_claims=True)
                else:
                    if not slide.reference_details:
                        raise ValidationError(f"Slide {slide.slide_number} has no evidence citation.")
                    resources_by_id = {resource.id: resource for resource in resources}
                    for reference in slide.reference_details:
                        self._validate_reference(slide.slide_number, reference, resources_by_id)
            else:
                # A user can author or alter a slide, but its new assertions
                # cannot inherit the model's evidence-verification label.
                slide.evidence_verified = False

    def _validate_reference(
        self,
        slide_number: int,
        reference: dict[str, object],
        resources_by_id: dict[str, Resource],
    ) -> None:
        resource_id = reference.get("resource_id")
        page_number = reference.get("page")
        excerpt = reference.get("evidence_excerpt")

        if not isinstance(resource_id, str) or resource_id not in resources_by_id:
            raise ValidationError(f"Slide {slide_number} cites an unknown resource ID.")
        if not isinstance(page_number, int):
            raise ValidationError(f"Slide {slide_number} citation has no valid PDF page.")
        if not isinstance(excerpt, str) or len(excerpt.strip()) < 12:
            raise ValidationError(f"Slide {slide_number} citation has no usable evidence excerpt.")

        resource = resources_by_id[resource_id]
        page_text = next(
            (
                page.get("text")
                for page in resource.extracted_pages
                if page.get("page") == page_number
            ),
            None,
        )
        if not isinstance(page_text, str):
            raise ValidationError(
                f"Slide {slide_number} cites page {page_number}, which does not exist in resource {resource_id}."
            )
        if self._normalize(excerpt) not in self._normalize(page_text):
            raise ValidationError(
                f"Slide {slide_number} evidence excerpt was not found on page {page_number} of resource {resource_id}."
            )

        label_pptx_reference(reference, resource)

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize comparison text without erasing Arabic or other Unicode scripts.

        Combining marks are removed so accented Latin text compares reliably,
        while letters from Arabic, Cyrillic and other scripts remain intact.
        """
        decomposed = unicodedata.normalize("NFKD", text)
        without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
        return "".join(char for char in without_marks.casefold() if char.isalnum())
