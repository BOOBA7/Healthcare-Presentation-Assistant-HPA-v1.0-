"""Local BM25 retrieval over text extracted only from user-provided PDFs."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log
import re

from app.domain.models.presentation import Presentation
from app.domain.models.slide_outline import SlideOutline


@dataclass(frozen=True)
class EvidenceChunk:
    resource_id: str
    page: int
    title: str
    position: int
    text: str
    terms: tuple[str, ...]


class EvidenceContextBuilder:
    """Retrieve compact, diverse evidence with deterministic local BM25 scoring."""

    max_chunks = 6
    max_chunks_per_resource = 2
    max_characters = 6_000
    chunk_characters = 1_200
    bm25_k1 = 1.2
    bm25_b = 0.75

    def for_presentation(self, presentation: Presentation) -> str:
        query = " ".join(
            [presentation.context.topic, presentation.context.objective, presentation.context.audience.value]
        )
        return self._select(presentation, query)

    def for_slide(self, presentation: Presentation, outline: SlideOutline) -> str:
        query = " ".join(
            [presentation.context.topic, outline.title, outline.objective, outline.key_message]
        )
        return self._select(presentation, query)

    def _select(self, presentation: Presentation, query: str) -> str:
        chunks = self._chunks_for_presentation(presentation)
        query_terms = self._terms(query)
        if not chunks or not query_terms:
            return "No relevant validated PDF passages are available."

        scores = self._bm25_scores(chunks, query_terms)
        ranked = sorted(
            zip(scores, chunks),
            key=lambda item: (-item[0], item[1].resource_id, item[1].page, item[1].position),
        )

        selected: list[str] = []
        selected_per_resource: Counter[str] = Counter()
        total_characters = 0
        for score, chunk in ranked:
            if score <= 0 or selected_per_resource[chunk.resource_id] >= self.max_chunks_per_resource:
                continue
            entry = self._format_chunk(chunk)
            if total_characters + len(entry) > self.max_characters:
                continue
            selected.append(entry)
            selected_per_resource[chunk.resource_id] += 1
            total_characters += len(entry)
            if len(selected) >= self.max_chunks:
                break

        return "\n\n".join(selected) or "No relevant validated PDF passages are available."

    def _chunks_for_presentation(self, presentation: Presentation) -> list[EvidenceChunk]:
        chunks: list[EvidenceChunk] = []
        for resource in presentation.resources:
            if not resource.is_validated:
                continue
            for page in resource.extracted_pages:
                page_number, page_text = page.get("page"), page.get("text")
                if not isinstance(page_number, int) or not isinstance(page_text, str):
                    continue
                for position, text in enumerate(self._split_chunks(page_text)):
                    terms = tuple(self._terms(text))
                    if terms:
                        chunks.append(
                            EvidenceChunk(
                                resource_id=resource.id,
                                page=page_number,
                                title=resource.title or resource.filename,
                                position=position,
                                text=text,
                                terms=terms,
                            )
                        )
        return chunks

    def _bm25_scores(self, chunks: list[EvidenceChunk], query_terms: list[str]) -> list[float]:
        document_frequency: Counter[str] = Counter()
        for chunk in chunks:
            document_frequency.update(set(chunk.terms))
        average_length = sum(len(chunk.terms) for chunk in chunks) / len(chunks)
        total_documents = len(chunks)
        query_frequency = Counter(query_terms)
        scores: list[float] = []
        for chunk in chunks:
            term_frequency = Counter(chunk.terms)
            score = 0.0
            for term, query_count in query_frequency.items():
                frequency = term_frequency[term]
                if not frequency:
                    continue
                inverse_document_frequency = log(1 + (total_documents - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
                denominator = frequency + self.bm25_k1 * (1 - self.bm25_b + self.bm25_b * len(chunk.terms) / average_length)
                score += query_count * inverse_document_frequency * (frequency * (self.bm25_k1 + 1) / denominator)
            scores.append(score)
        return scores

    def _format_chunk(self, chunk: EvidenceChunk) -> str:
        return (
            "BEGIN UNTRUSTED SOURCE EXCERPT\n"
            f"SOURCE ID: {chunk.resource_id} | TITLE: {chunk.title} | PAGE: {chunk.page}\n"
            f"{chunk.text}\n"
            "END UNTRUSTED SOURCE EXCERPT"
        )

    def _split_chunks(self, text: str) -> list[str]:
        normalized = " ".join(text.split())
        return [
            normalized[index : index + self.chunk_characters]
            for index in range(0, len(normalized), self.chunk_characters)
            if normalized[index : index + self.chunk_characters].strip()
        ]

    @staticmethod
    def _terms(text: str) -> list[str]:
        return re.findall(r"[\wÀ-ÿ]{3,}", text.casefold())
