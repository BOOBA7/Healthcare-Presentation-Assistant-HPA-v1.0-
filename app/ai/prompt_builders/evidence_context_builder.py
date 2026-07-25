"""Deterministic, lightweight retrieval over text extracted from user PDFs."""

import re

from app.domain.models.presentation import Presentation
from app.domain.models.slide_outline import SlideOutline


class EvidenceContextBuilder:
    """Select compact, relevant PDF passages instead of injecting entire documents."""

    max_chunks = 6
    max_characters = 6_000
    chunk_characters = 1_200

    def for_presentation(self, presentation: Presentation) -> str:
        query = " ".join(
            [
                presentation.context.topic,
                presentation.context.objective,
                presentation.context.audience.value,
            ]
        )
        return self._select(presentation, query)

    def for_slide(self, presentation: Presentation, outline: SlideOutline) -> str:
        query = " ".join(
            [
                presentation.context.topic,
                outline.title,
                outline.objective,
                outline.key_message,
            ]
        )
        return self._select(presentation, query)

    def _select(self, presentation: Presentation, query: str) -> str:
        query_terms = set(self._terms(query))
        candidates: list[tuple[int, str, int, str, str]] = []

        for resource in presentation.resources:
            for page in resource.extracted_pages:
                page_number = page.get("page")
                page_text = page.get("text")
                if not isinstance(page_number, int) or not isinstance(page_text, str):
                    continue
                for chunk in self._chunks(page_text):
                    score = len(query_terms.intersection(self._terms(chunk)))
                    candidates.append(
                        (score, resource.id, page_number, resource.title or resource.filename, chunk)
                    )

        if not candidates:
            return "No extracted PDF passages are available."

        candidates.sort(key=lambda item: item[0], reverse=True)
        selected: list[str] = []
        total_characters = 0
        for _, resource_id, page_number, title, chunk in candidates:
            entry = f"SOURCE ID: {resource_id} | TITLE: {title} | PAGE: {page_number}\n{chunk.strip()}"
            if total_characters + len(entry) > self.max_characters:
                continue
            selected.append(entry)
            total_characters += len(entry)
            if len(selected) >= self.max_chunks:
                break

        return "\n\n".join(selected) or "No relevant PDF passages are available."

    def _chunks(self, text: str) -> list[str]:
        normalized = " ".join(text.split())
        return [
            normalized[index : index + self.chunk_characters]
            for index in range(0, len(normalized), self.chunk_characters)
            if normalized[index : index + self.chunk_characters].strip()
        ]

    @staticmethod
    def _terms(text: str) -> list[str]:
        return re.findall(r"[\wÀ-ÿ]{3,}", text.lower())
