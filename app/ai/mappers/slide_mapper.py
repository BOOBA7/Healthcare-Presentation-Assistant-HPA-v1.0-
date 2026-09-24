from app.ai.schemas.slide_schema import SlideSchema
from app.domain.models.slide import Slide
from app.domain.models.claim_evidence import EvidenceLink, MedicalClaim
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

        claims = []
        links = []
        seen = set()
        for index, reference in enumerate(schema.references, start=1):
            if reference.claim_id not in seen:
                claims.append(MedicalClaim(id=reference.claim_id, text=PresentationDeidentification.text(reference.claim_text)))
                seen.add(reference.claim_id)
            if reference.resource_id and reference.page and reference.evidence_excerpt:
                links.append(EvidenceLink(
                    id=f"{reference.claim_id}-evidence-{index}", claim_id=reference.claim_id,
                    claim_revision=1, resource_id=reference.resource_id,
                    resource_title=PresentationDeidentification.text(reference.title), location_kind=reference.location_kind,
                    location_number=reference.page, section=reference.section,
                    exact_passage=PresentationDeidentification.text(reference.evidence_excerpt), doi=reference.doi,
                    url=PresentationDeidentification.text(reference.url),
                ))
        return Slide(
            slide_number=schema.slide_number,
            title=PresentationDeidentification.text(schema.title),
            objective=PresentationDeidentification.text(schema.objective),
            key_messages=PresentationDeidentification.value(schema.key_messages),
            content=PresentationDeidentification.text(schema.content),
            speaker_notes=PresentationDeidentification.text(schema.speaker_notes),
            references=[PresentationDeidentification.text(reference.title) for reference in schema.references],
            reference_details=[PresentationDeidentification.value(reference.model_dump()) for reference in schema.references],
            claims=claims,
            evidence_links=links,
            visual_recommendations=PresentationDeidentification.value(schema.visual_recommendations),
            is_validated=False,
        )
