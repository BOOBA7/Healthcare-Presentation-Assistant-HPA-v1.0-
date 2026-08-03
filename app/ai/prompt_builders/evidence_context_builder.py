"""Local BM25 retrieval over text extracted only from user-provided PDFs."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log
import re

from app.domain.models.presentation import Presentation
from app.domain.models.resource import Resource
from app.domain.models.resource_chunk import ResourceChunk
from app.domain.models.slide_outline import SlideOutline
from app.application.services.observability import record
from app.domain.enums.evidence_context_mode import EvidenceContextMode


@dataclass(frozen=True)
class EvidenceChunk:
    resource_id: str
    page: int
    title: str
    position: int
    text: str
    terms: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceAssessment:
    """Deterministic retrieval decision used before scientific generation."""

    has_validated_resources: bool
    is_sufficient: bool
    best_score: float
    matched_terms: tuple[str, ...]


class EvidenceContextBuilder:
    """Retrieve compact, diverse evidence with deterministic local BM25 scoring."""

    max_chunks = 6
    max_chunks_per_resource = 2
    max_characters = 6_000
    chunk_characters = 1_200
    bm25_k1 = 1.2
    bm25_b = 0.75

    def for_presentation(
        self,
        presentation: Presentation,
        resources: list[Resource] | None = None,
        chunks: list[ResourceChunk] | None = None,
    ) -> str:
        query = " ".join(
            [presentation.context.topic, presentation.context.objective, presentation.context.audience.value]
        )
        return self._select(
            resources or presentation.resources,
            query,
            chunks,
            presentation.evidence_context_mode,
        )

    def for_slide(
        self,
        presentation: Presentation,
        outline: SlideOutline,
        resources: list[Resource] | None = None,
        chunks: list[ResourceChunk] | None = None,
    ) -> str:
        query = " ".join(
            [presentation.context.topic, outline.title, outline.objective, outline.key_message]
        )
        return self._select(
            resources or presentation.resources,
            query,
            chunks,
            presentation.evidence_context_mode,
        )

    def assess(
        self,
        presentation: Presentation,
        query: str,
        resources: list[Resource] | None = None,
        chunks: list[ResourceChunk] | None = None,
    ) -> EvidenceAssessment:
        """Return whether local, validated evidence sufficiently covers a query.

        This is deliberately deterministic: a model cannot turn missing evidence
        into a supported answer by sounding confident.
        """
        evidence_chunks = self._chunks_for_resources(resources or presentation.resources, chunks)
        query_terms = tuple(dict.fromkeys(self._terms(query)))
        if not evidence_chunks:
            return EvidenceAssessment(False, False, 0.0, ())
        if not query_terms:
            return EvidenceAssessment(True, False, 0.0, ())

        mode = presentation.evidence_context_mode
        candidates = (
            self._direct_chunks(evidence_chunks)
            if mode == EvidenceContextMode.DIRECT_BOUNDED
            else evidence_chunks
        )
        if not candidates:
            return EvidenceAssessment(True, False, 0.0, ())
        if mode == EvidenceContextMode.DIRECT_BOUNDED:
            available_terms = set().union(*(set(chunk.terms) for chunk in candidates))
            matched_terms = tuple(sorted(set(query_terms).intersection(available_terms)))
            best_score = len(matched_terms) / len(query_terms)
        else:
            scores = self._bm25_scores(candidates, list(query_terms))
            best_index, best_score = max(enumerate(scores), key=lambda item: item[1])
            matched_terms = tuple(sorted(set(query_terms).intersection(candidates[best_index].terms)))
        minimum_matches = 1 if len(query_terms) <= 2 else 2
        return EvidenceAssessment(
            has_validated_resources=True,
            is_sufficient=best_score > 0 and len(matched_terms) >= minimum_matches,
            best_score=best_score,
            matched_terms=matched_terms,
        )

    def for_resources(
        self,
        resources: list[Resource],
        query: str,
        chunks: list[ResourceChunk] | None = None,
        mode: EvidenceContextMode = EvidenceContextMode.BM25,
    ) -> str:
        """Retrieve bounded, cited passages for Project-library exploration."""
        return self._select(resources, query, chunks, mode)

    def for_overview(
        self,
        resources: list[Resource],
        chunks: list[ResourceChunk] | None = None,
        mode: EvidenceContextMode = EvidenceContextMode.BM25,
    ) -> str:
        """Build a balanced bounded context for a resource-library overview."""
        evidence_chunks = self._chunks_for_resources(resources, chunks)
        if mode == EvidenceContextMode.DIRECT_BOUNDED:
            return self._format_selected(
                self._direct_chunks(evidence_chunks),
                purpose="overview",
                mode=mode,
            )
        selected: list[str] = []
        selected_chunks: list[EvidenceChunk] = []
        total = 0
        # One first chunk and one middle chunk per resource avoids the old
        # first-page-only bias while keeping the prompt bounded.
        by_resource: dict[str, list[EvidenceChunk]] = {}
        for chunk in evidence_chunks:
            by_resource.setdefault(chunk.resource_id, []).append(chunk)
        for resource_id in sorted(by_resource):
            candidates = by_resource[resource_id]
            for chunk in (candidates[0], candidates[len(candidates) // 2]):
                entry = self._format_chunk(chunk)
                if entry not in selected and total + len(entry) <= self.max_characters:
                    selected.append(entry)
                    selected_chunks.append(chunk)
                    total += len(entry)
        context = "\n\n".join(selected) or "No relevant validated PDF passages are available."
        record(
            "bm25_retrieval",
            purpose="overview",
            mode=mode.value,
            selected_passages=len(selected_chunks),
            resource_ids=sorted(by_resource),
            context_characters=len(context),
        )
        return context

    def _select(
        self,
        resources: list[Resource],
        query: str,
        persisted_chunks: list[ResourceChunk] | None = None,
        mode: EvidenceContextMode = EvidenceContextMode.BM25,
    ) -> str:
        chunks = self._chunks_for_resources(resources, persisted_chunks)
        query_terms = self._terms(query)
        if not chunks or not query_terms:
            return "No relevant validated PDF passages are available."

        if mode == EvidenceContextMode.DIRECT_BOUNDED:
            return self._format_selected(
                self._direct_chunks(chunks),
                purpose="query",
                mode=mode,
                query_terms=query_terms,
            )

        scores = self._bm25_scores(chunks, query_terms)
        ranked = sorted(
            zip(scores, chunks),
            key=lambda item: (-item[0], item[1].resource_id, item[1].page, item[1].position),
        )

        selected: list[str] = []
        selected_chunks: list[EvidenceChunk] = []
        selected_per_resource: Counter[str] = Counter()
        total_characters = 0
        for score, chunk in ranked:
            if score <= 0 or selected_per_resource[chunk.resource_id] >= self.max_chunks_per_resource:
                continue
            entry = self._format_chunk(chunk)
            if total_characters + len(entry) > self.max_characters:
                continue
            selected.append(entry)
            selected_chunks.append(chunk)
            selected_per_resource[chunk.resource_id] += 1
            total_characters += len(entry)
            if len(selected) >= self.max_chunks:
                break

        context = "\n\n".join(selected) or "No relevant validated PDF passages are available."
        record(
            "bm25_retrieval",
            purpose="query",
            mode=mode.value,
            query_terms=len(set(query_terms)),
            selected_passages=len(selected_chunks),
            selected_locations=[f"{chunk.resource_id}:p{chunk.page}" for chunk in selected_chunks],
            context_characters=len(context),
        )
        return context

    def _direct_chunks(self, chunks: list[EvidenceChunk]) -> list[EvidenceChunk]:
        """Use a deterministic, source-balanced window without relevance ranking.

        This is intentionally an experimental *direct bounded context* mode:
        it does not score, rank, or query-select passages. It still retains the
        same source/page metadata and hard context limit as BM25 mode.
        """
        by_resource: dict[str, list[EvidenceChunk]] = {}
        for chunk in sorted(chunks, key=lambda item: (item.resource_id, item.page, item.position)):
            by_resource.setdefault(chunk.resource_id, []).append(chunk)
        indexes = {resource_id: 0 for resource_id in by_resource}
        selected: list[EvidenceChunk] = []
        total_characters = 0
        while len(selected) < self.max_chunks:
            added = False
            for resource_id in sorted(by_resource):
                index = indexes[resource_id]
                candidates = by_resource[resource_id]
                if index >= len(candidates):
                    continue
                candidate = candidates[index]
                indexes[resource_id] += 1
                entry = self._format_chunk(candidate)
                if total_characters + len(entry) > self.max_characters:
                    continue
                selected.append(candidate)
                total_characters += len(entry)
                added = True
                if len(selected) >= self.max_chunks:
                    break
            if not added:
                break
        return selected

    def _format_selected(
        self,
        chunks: list[EvidenceChunk],
        *,
        purpose: str,
        mode: EvidenceContextMode,
        query_terms: list[str] | None = None,
    ) -> str:
        context = "\n\n".join(self._format_chunk(chunk) for chunk in chunks)
        if not context:
            return "No relevant validated PDF passages are available."
        record(
            "evidence_context",
            purpose=purpose,
            mode=mode.value,
            query_terms=len(set(query_terms or [])),
            selected_passages=len(chunks),
            selected_locations=[f"{chunk.resource_id}:p{chunk.page}" for chunk in chunks],
            context_characters=len(context),
        )
        return context

    def _chunks_for_resources(
        self, resources: list[Resource], persisted_chunks: list[ResourceChunk] | None = None
    ) -> list[EvidenceChunk]:
        validated_resources = {resource.id for resource in resources if resource.is_validated}
        # An empty cache means this state has not been hydrated from SQLite
        # yet (for example an in-memory unit test or a freshly created state).
        # Fall back to in-state pages only in that compatibility case.
        if persisted_chunks:
            return [
                EvidenceChunk(
                    resource_id=chunk.resource_id,
                    page=chunk.page,
                    title=chunk.title,
                    position=chunk.position,
                    text=chunk.text,
                    terms=tuple(self._terms(chunk.text)),
                )
                for chunk in persisted_chunks
                if chunk.resource_id in validated_resources and self._terms(chunk.text)
            ]
        chunks: list[EvidenceChunk] = []
        for resource in resources:
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
