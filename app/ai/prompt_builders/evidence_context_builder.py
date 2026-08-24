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
class EvidenceSelection:
    """Passages selected for one task before the common evidence decision."""

    mode: EvidenceContextMode
    query_terms: tuple[str, ...]
    chunks: tuple[EvidenceChunk, ...]
    retrieval_scores: tuple[float, ...]


@dataclass(frozen=True)
class EvidenceAssessment:
    """Mode-independent sufficiency decision used before scientific generation."""

    has_validated_resources: bool
    is_sufficient: bool
    best_score: float
    matched_terms: tuple[str, ...]
    mode: EvidenceContextMode
    query_term_count: int
    required_matches: int
    selected_locations: tuple[str, ...]
    anchor_location: str | None = None
    selection_scores: tuple[float, ...] = ()

    def diagnostic(self) -> dict[str, object]:
        """Return safe metadata for an audit record or an actionable UI blocker."""
        return {
            "mode": self.mode.value,
            "query_term_count": self.query_term_count,
            "required_matches": self.required_matches,
            "matched_term_count": len(self.matched_terms),
            "selected_locations": list(self.selected_locations),
            "selection_scores": [round(score, 4) for score in self.selection_scores],
            "anchor_location": self.anchor_location,
        }


class EvidenceContextBuilder:
    """Retrieve compact, diverse evidence with deterministic local BM25 scoring."""

    max_chunks = 6
    max_chunks_per_resource = 2
    max_characters = 6_000
    chunk_characters = 1_200
    bm25_k1 = 1.2
    bm25_b = 0.75

    @staticmethod
    def presentation_query(presentation: Presentation) -> str:
        """Single source of truth for blueprint gate and prompt retrieval."""
        return " ".join(
            [
                presentation.context.topic,
                presentation.context.objective,
                presentation.context.audience.value,
            ]
        )

    @staticmethod
    def slide_query(presentation: Presentation, outline: SlideOutline) -> str:
        """Single source of truth for slide gate and prompt retrieval."""
        return " ".join(
            [
                presentation.context.topic,
                outline.title,
                outline.objective,
                outline.key_message,
            ]
        )

    def for_presentation(
        self,
        presentation: Presentation,
        resources: list[Resource] | None = None,
        chunks: list[ResourceChunk] | None = None,
    ) -> str:
        query = self.presentation_query(presentation)
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
        query = self.slide_query(presentation, outline)
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
        mode = presentation.evidence_context_mode
        if not evidence_chunks:
            return EvidenceAssessment(False, False, 0.0, (), mode, len(query_terms), 0, ())
        if not query_terms:
            return EvidenceAssessment(True, False, 0.0, (), mode, 0, 0, ())

        selection = self._select_query_chunks(evidence_chunks, query_terms, mode)
        assessment = self._assess_selected_chunks(selection, has_validated_resources=True)
        record("evidence_assessment", purpose="generation_gate", **assessment.diagnostic())
        return assessment

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
        query_terms = tuple(dict.fromkeys(self._terms(query)))
        if not chunks or not query_terms:
            return "No relevant validated PDF passages are available."
        selection = self._select_query_chunks(chunks, query_terms, mode)
        context = "\n\n".join(self._format_chunk(chunk) for chunk in selection.chunks)
        record(
            "evidence_selection",
            purpose="query",
            mode=mode.value,
            query_terms=len(selection.query_terms),
            selected_passages=len(selection.chunks),
            selected_locations=[f"{chunk.resource_id}:p{chunk.page}" for chunk in selection.chunks],
            selection_scores=[round(score, 4) for score in selection.retrieval_scores],
            context_characters=len(context),
        )
        return context or "No relevant validated PDF passages are available."

    def _select_query_chunks(
        self,
        chunks: list[EvidenceChunk],
        query_terms: tuple[str, ...],
        mode: EvidenceContextMode,
    ) -> EvidenceSelection:
        """Select bounded passages; this never decides whether evidence is sufficient."""
        if mode == EvidenceContextMode.DIRECT_BOUNDED:
            selected = self._direct_chunks(chunks)
            return EvidenceSelection(
                mode=mode,
                query_terms=query_terms,
                chunks=tuple(selected),
                retrieval_scores=tuple(0.0 for _ in selected),
            )

        scores = self._bm25_scores(chunks, list(query_terms))
        ranked = sorted(
            zip(scores, chunks),
            key=lambda item: (-item[0], item[1].resource_id, item[1].page, item[1].position),
        )
        selected: list[EvidenceChunk] = []
        selected_scores: list[float] = []
        selected_per_resource: Counter[str] = Counter()
        total_characters = 0
        for score, chunk in ranked:
            if score <= 0 or selected_per_resource[chunk.resource_id] >= self.max_chunks_per_resource:
                continue
            entry = self._format_chunk(chunk)
            if total_characters + len(entry) > self.max_characters:
                continue
            selected.append(chunk)
            selected_scores.append(score)
            selected_per_resource[chunk.resource_id] += 1
            total_characters += len(entry)
            if len(selected) >= self.max_chunks:
                break
        return EvidenceSelection(
            mode=mode,
            query_terms=query_terms,
            chunks=tuple(selected),
            retrieval_scores=tuple(selected_scores),
        )

    @staticmethod
    def _assess_selected_chunks(
        selection: EvidenceSelection,
        *,
        has_validated_resources: bool,
    ) -> EvidenceAssessment:
        """Apply the exact same evidence rule after either retrieval strategy.

        A supporting anchor must exist in one selected passage. Pooling partial
        matches across unrelated passages would make one mode less strict than
        the other and would not identify an auditable source for the slide.
        """
        minimum_matches = 1 if len(selection.query_terms) <= 2 else 2
        locations = tuple(f"{chunk.resource_id}:p{chunk.page}" for chunk in selection.chunks)
        candidates: list[tuple[int, float, EvidenceChunk, tuple[str, ...]]] = []
        query_terms = set(selection.query_terms)
        for index, chunk in enumerate(selection.chunks):
            matches = tuple(sorted(query_terms.intersection(chunk.terms)))
            retrieval_score = selection.retrieval_scores[index] if index < len(selection.retrieval_scores) else 0.0
            candidates.append((len(matches), retrieval_score, chunk, matches))
        if not candidates:
            return EvidenceAssessment(
                has_validated_resources,
                False,
                0.0,
                (),
                selection.mode,
                len(selection.query_terms),
                minimum_matches,
                locations,
                selection_scores=selection.retrieval_scores,
            )

        _, _, anchor, matched_terms = max(
            candidates,
            key=lambda item: (item[0], item[1], -item[2].page, -item[2].position),
        )
        coverage_score = len(matched_terms) / len(selection.query_terms)
        return EvidenceAssessment(
            has_validated_resources,
            len(matched_terms) >= minimum_matches,
            coverage_score,
            matched_terms,
            selection.mode,
            len(selection.query_terms),
            minimum_matches,
            locations,
            anchor_location=f"{anchor.resource_id}:p{anchor.page}",
            selection_scores=selection.retrieval_scores,
        )

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
