from app.ai.schemas.slide_schema import SlideSchema
from app.domain.models.slide import Slide
from app.domain.models.claim_evidence import EvidenceLink, MedicalClaim
from app.domain.value_objects.speaker_note import SpeakerNote
from app.application.services.presentation_deidentification import PresentationDeidentification


class SlideMapper:
    """
    Converts an AI SlideSchema into
    the domain Slide model.
    """

    def to_domain(
        self,
        schema: SlideSchema,
    ) -> Slide:

        claims, links = self._map_evidence(schema.references, "slide")
        note_claims, note_links = self._map_evidence(schema.speaker_note_references, "note")
        return Slide(
            slide_number=schema.slide_number,
            title=PresentationDeidentification.text(schema.title),
            objective=PresentationDeidentification.text(schema.objective),
            key_messages=PresentationDeidentification.value(schema.key_messages),
            content=PresentationDeidentification.text(schema.content),
            speaker_notes=PresentationDeidentification.text(schema.speaker_notes),
            speaker_note=SpeakerNote(
                text=PresentationDeidentification.text(schema.speaker_notes),
                claims=note_claims,
                evidence_links=note_links,
            ),
            references=[PresentationDeidentification.text(reference.title) for reference in schema.references],
            reference_details=[PresentationDeidentification.value(reference.model_dump()) for reference in schema.references],
            claims=claims,
            evidence_links=links,
            visual_recommendations=PresentationDeidentification.value(schema.visual_recommendations),
            is_validated=False,
        )

    @staticmethod
    def _map_evidence(references, prefix: str):
        claims = []
        links = []
        seen = set()
        for index, reference in enumerate(references, start=1):
            if reference.claim_id not in seen:
                claims.append(MedicalClaim(
                    id=reference.claim_id,
                    text=PresentationDeidentification.text(reference.claim_text),
                    value=reference.claim_value,
                    unit=reference.claim_unit,
                    uncertainty=reference.claim_uncertainty,
                    missing_value=reference.missing_value,
                    conflict_group_id=reference.conflict_group_id,
                    source_position=reference.source_position,
                ))
                seen.add(reference.claim_id)
            if reference.resource_id and reference.page and reference.evidence_excerpt:
                links.append(EvidenceLink(
                    id=f"{prefix}-{reference.claim_id}-evidence-{index}", claim_id=reference.claim_id,
                    claim_revision=1, resource_id=reference.resource_id,
                    resource_title=PresentationDeidentification.text(reference.title), location_kind=reference.location_kind,
                    location_number=reference.page, section=reference.section,
                    exact_passage=PresentationDeidentification.text(reference.evidence_excerpt), doi=reference.doi,
                    url=PresentationDeidentification.text(reference.url),
                ))
        return claims, links
