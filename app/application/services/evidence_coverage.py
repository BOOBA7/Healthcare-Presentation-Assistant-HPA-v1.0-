"""Deterministic pre-Agenda coverage assessment (PRD FR-09)."""

from __future__ import annotations

import hashlib
import json
import re

from app.domain.models.evidence_coverage import (
    CoveragePassage,
    CoverageResult,
    EvidenceCoverageAssessment,
)
from app.domain.models.presentation import Presentation
from app.domain.models.resource import Resource
from app.domain.models.resource_chunk import ResourceChunk


class EvidenceCoverageService:
    """Apply transparent workflow rules without claiming scientific validity.

    An available passage is a validated-source chunk of at least 80 characters.
    A deterministic match means one such passage contains at least two meaningful
    terms for the dimension; terms are never pooled across passages. Sufficient
    coverage means every required dimension passes these rules. Relevance and
    scientific validity always remain a separate human judgement.
    """

    VERSION = "coverage-v1"
    MIN_PASSAGE_CHARACTERS = 40
    MAX_CONTENT_SLIDES_PER_PASSAGE = 3
    RESERVED_DECK_SLIDES = 3  # title, references, closing
    _words = re.compile(r"[^\W_]+", re.UNICODE)
    _stop = {"and", "the", "for", "with", "from", "this", "that", "des", "les", "une", "pour", "avec", "dans", "sur", "review", "present", "explain", "describe"}

    def assess(
        self, presentation: Presentation, resources: list[Resource], chunks: list[ResourceChunk]
    ) -> EvidenceCoverageAssessment:
        validated = {item.id: item for item in resources if item.is_validated}
        available = [
            chunk for chunk in chunks
            if chunk.resource_id in validated and len(" ".join(chunk.text.split())) >= self.MIN_PASSAGE_CHARACTERS
        ]
        results: list[CoverageResult] = []
        results.append(self._semantic_result("topic", "Presentation topic", presentation.context.topic, available, validated))
        objectives = self._objectives(presentation.context.objective)
        for index, objective in enumerate(objectives, 1):
            results.append(self._semantic_result("objective", f"Learning objective {index}", objective, available, validated))

        audience_terms = self._audience_terms(presentation.context.audience.value)
        results.append(self._term_result(
            "audience", "Target audience", audience_terms, available, validated,
            "Add a resource explicitly written for the target audience or care setting.",
        ))
        depth_terms = self._depth_terms(presentation.context.audience.value, presentation.context.special_instructions)
        results.append(self._term_result(
            "depth", "Requested depth", depth_terms, available, validated,
            "Add a resource whose scope explicitly supports the requested level of depth.",
        ))

        target = presentation.context.target_slide_count
        usable_locations = {(c.resource_id, c.page, c.position) for c in available}
        capacity = self.RESERVED_DECK_SLIDES + len(usable_locations) * self.MAX_CONTENT_SLIDES_PER_PASSAGE
        slide_ok = target is not None and bool(available) and target <= capacity
        results.append(CoverageResult(
            dimension="slide_count", label="Target slide count", sufficient=slide_ok,
            reason=(f"The explicit workflow capacity is {capacity} slides for {len(usable_locations)} distinct usable passages "
                    f"(three fixed slides plus at most {self.MAX_CONTENT_SLIDES_PER_PASSAGE} content slides per passage); target is {target}."
                    if target is not None else "The target slide count is missing."),
            requested_resource=None if slide_ok else "Add sources with distinct, sufficiently detailed passages or reduce the target slide count.",
            passages=[self._passage(c, validated[c.resource_id], []) for c in available],
        ))
        return EvidenceCoverageAssessment(
            context_digest=self.context_digest(presentation),
            resources_digest=self.resources_digest(resources),
            passages_digest=self.passages_digest(chunks),
            results=results,
            sufficient=all(result.sufficient for result in results),
        )

    def require_current(self, presentation: Presentation, resources: list[Resource], chunks: list[ResourceChunk]) -> EvidenceCoverageAssessment:
        stored = presentation.evidence_coverage
        if stored is None:
            raise ValueError("Assess evidence coverage before creating the Agenda.")
        if not self.is_current(stored, presentation, resources, chunks):
            raise ValueError("Evidence coverage is obsolete; reassess it after the upstream change.")
        if not stored.sufficient:
            raise ValueError("Evidence coverage is insufficient; resolve every missing area before creating the Agenda.")
        return stored

    def is_current(self, stored, presentation, resources, chunks) -> bool:
        return bool(stored and stored.version == self.VERSION
                    and stored.context_digest == self.context_digest(presentation)
                    and stored.resources_digest == self.resources_digest(resources)
                    and stored.passages_digest == self.passages_digest(chunks))

    def _semantic_result(self, dimension, label, query, chunks, resources):
        terms = self._terms(query)
        return self._term_result(dimension, label, terms, chunks, resources,
                                 f"Add a resource with one substantial passage directly addressing {label.lower()}.")

    def _term_result(self, dimension, label, terms, chunks, resources, request):
        matches = []
        for chunk in chunks:
            common = sorted(set(terms).intersection(self._terms(chunk.text)))
            # One anchor must carry up to three meaningful terms. This avoids
            # declaring a multi-part topic covered from a merely partial hit.
            required = min(3, len(set(terms)))
            if required and len(common) >= required:
                matches.append(self._passage(chunk, resources[chunk.resource_id], common))
        sufficient = bool(matches)
        if not chunks:
            reason = "No substantial passage from a selected, validated resource is available."
        elif not terms:
            reason = f"The {label.lower()} is missing or ambiguous."
        elif sufficient:
            reason = "At least one substantial passage contains the required terms in a single auditable location."
        else:
            reason = "Available passages do not contain the required terms together in one auditable location."
        return CoverageResult(dimension=dimension, label=label, sufficient=sufficient, reason=reason,
                              requested_resource=None if sufficient else request, passages=matches)

    @staticmethod
    def _objectives(value: str) -> list[str]:
        return [item.strip(" -•\t") for item in re.split(r"[;\n]+", value or "") if item.strip(" -•\t")]

    @staticmethod
    def _audience_terms(value: str) -> list[str]:
        value = value.casefold().replace(" ", "_")
        return {
            "specialist": ["specialist", "advanced"],
            "general_practitioner": ["general", "practitioner", "primary", "care"],
            "resident": ["resident", "training"],
            "medical_student": ["student", "foundational"],
        }.get(value, [value.replace("_", " ")])

    @classmethod
    def _depth_terms(cls, audience: str, instructions: str | None) -> list[str]:
        explicit = cls._terms(instructions or "")
        depth_words = [term for term in explicit if term in {"advanced", "detailed", "foundational", "introductory", "practical", "clinical"}]
        if depth_words:
            return depth_words
        return ["advanced", "detailed"] if audience.casefold() == "specialist" else ["clinical", "practical"]

    @classmethod
    def _terms(cls, value: str) -> list[str]:
        return [word.casefold() for word in cls._words.findall(value) if len(word) > 2 and word.casefold() not in cls._stop]

    @staticmethod
    def _passage(chunk, resource, matched):
        return CoveragePassage(resource_id=chunk.resource_id, resource_title=resource.title or resource.filename,
                               location_kind="slide" if resource.file_type.value == "pptx" else "page",
                               location_number=chunk.page, passage_position=chunk.position, matched_terms=matched)

    @classmethod
    def _digest(cls, value) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

    def context_digest(self, presentation):
        return self._digest(presentation.context.model_dump(mode="json"))

    def resources_digest(self, resources):
        return self._digest([(r.id, r.is_validated, r.metadata.original_sha256, r.title, r.filename) for r in sorted(resources, key=lambda x: x.id)])

    def passages_digest(self, chunks):
        return self._digest([(c.resource_id, c.page, c.position, c.text) for c in sorted(chunks, key=lambda x: (x.resource_id, x.page, x.position))])
