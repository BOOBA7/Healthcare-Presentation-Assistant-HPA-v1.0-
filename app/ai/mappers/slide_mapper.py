from app.ai.schemas.slide_schema import SlideSchema
from app.domain.models.slide import Slide
from app.domain.models.claim_evidence import EvidenceLink, MedicalClaim


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
                claims.append(MedicalClaim(id=reference.claim_id, text=reference.claim_text))
                seen.add(reference.claim_id)
            if reference.resource_id and reference.page and reference.evidence_excerpt:
                links.append(EvidenceLink(
                    id=f"{reference.claim_id}-evidence-{index}", claim_id=reference.claim_id,
                    claim_revision=1, resource_id=reference.resource_id,
                    resource_title=reference.title, location_kind=reference.location_kind,
                    location_number=reference.page, section=reference.section,
                    exact_passage=reference.evidence_excerpt, doi=reference.doi, url=reference.url,
                ))
        return Slide(
            slide_number=schema.slide_number,
            title=schema.title,
            objective=schema.objective,
            key_messages=schema.key_messages,
            content=schema.content,
            speaker_notes=schema.speaker_notes,
            references=[reference.title for reference in schema.references],
            reference_details=[reference.model_dump() for reference in schema.references],
            claims=claims,
            evidence_links=links,
            visual_recommendations=schema.visual_recommendations,
            is_validated=False,
        )
