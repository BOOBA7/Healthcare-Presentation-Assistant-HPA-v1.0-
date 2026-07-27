"""Deterministic checks for evidence citations produced by the language model."""

import re
import unicodedata

from app.domain.models.resource import Resource
from app.domain.models.slide import Slide


class EvidenceProvenanceValidator:
    """Accept a citation only when it points to an exact uploaded PDF passage."""

    def validate_slide(self, slide: Slide, resources: list[Resource]) -> None:
        if not slide.reference_details:
            raise ValueError(f"Slide {slide.slide_number} has no evidence citation.")

        resources_by_id = {resource.id: resource for resource in resources}
        for reference in slide.reference_details:
            self._validate_reference(slide.slide_number, reference, resources_by_id)

        slide.evidence_verified = True

    def validate_presentation(self, slides: list[Slide], resources: list[Resource]) -> None:
        for slide in slides:
            if slide.content_origin == "ai_generated":
                self.validate_slide(slide, resources)
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
            raise ValueError(f"Slide {slide_number} cites an unknown resource ID.")
        if not isinstance(page_number, int):
            raise ValueError(f"Slide {slide_number} citation has no valid PDF page.")
        if not isinstance(excerpt, str) or len(excerpt.strip()) < 12:
            raise ValueError(f"Slide {slide_number} citation has no usable evidence excerpt.")

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
            raise ValueError(
                f"Slide {slide_number} cites page {page_number}, which does not exist in resource {resource_id}."
            )
        if self._normalize(excerpt) not in self._normalize(page_text):
            raise ValueError(
                f"Slide {slide_number} evidence excerpt was not found on page {page_number} of resource {resource_id}."
            )

    @staticmethod
    def _normalize(text: str) -> str:
        decomposed = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]+", "", decomposed.lower())
