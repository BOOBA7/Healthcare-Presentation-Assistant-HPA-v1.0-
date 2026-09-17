"""Transparent FR-10/FR-19 comparison and transfer rules."""

from __future__ import annotations

import hashlib
import json
import re

from app.application.services.evidence_coverage import EvidenceCoverageService
from app.application.validators.response_citation_validator import ResponseCitationValidator
from app.domain.models.conversation_turn import ConversationTurn
from app.domain.models.discussion_transfer import DiscussionComparison, DiscussionPosition, PlanningTransfer


class DiscussionTransferService:
    """Keep scientific interpretation human while enforcing workflow provenance."""

    CONFLICT_VERSION = "discussion-conflict-v1"
    TRANSFER_VERSION = "discussion-transfer-v1"
    # The only established-conflict rule is exact normalized identity after
    # removing one explicit English/French negation token. Everything else is
    # merely a potential comparison; recency, count and model wording never rank it.
    _negation = re.compile(r"\b(not|no|ne|pas|non)\b", re.IGNORECASE)
    _space = re.compile(r"[^\w]+", re.UNICODE)

    def comparisons(self, history: list[ConversationTurn], resources) -> list[DiscussionComparison]:
        assistant = next((t.text for t in reversed(history) if t.role == "assistant"), None)
        if not assistant:
            return []
        try:
            citations = ResponseCitationValidator().validate(assistant, resources)
        except ValueError:
            return []
        positions = [self._position(c, resources) for c in citations]
        if len(positions) < 2:
            return []
        signatures = [self._signature(p.exact_passage) for p in positions]
        negated = [bool(self._negation.search(p.exact_passage)) for p in positions]
        established = len(set(signatures)) == 1 and len(set(negated)) > 1
        classification = "deterministic_conflict" if established else "potential_conflict"
        rule = ("Exact normalized statements differ only by an explicit negation token."
                if established else
                "The cited passages differ; population, context, date, wording and purpose require human comparison.")
        return [DiscussionComparison(classification=classification, rule=rule, positions=positions)]

    def create_transfer(self, state, destination, content, retained_ids, uncertainties, actor):
        if state.presentation is None or state.presentation.evidence_coverage is None:
            raise ValueError("A current evidence-coverage assessment is required before transfer.")
        resources = self._selected(state)
        coverage = EvidenceCoverageService()
        coverage.require_current(state.presentation, resources, state.resource_chunks)
        comparisons = self.comparisons(state.resource_conversation_history, resources)
        available = {p.id: p for c in comparisons for p in c.positions}
        if not retained_ids or any(item not in available for item in retained_ids):
            raise ValueError("Every transferred position must be selected from the current verified discussion.")
        if any(c.classification != "different_passages" and not {p.id for p in c.positions}.issubset(retained_ids)
               for c in comparisons):
            raise ValueError("Conflicting or potentially conflicting positions must be retained together.")
        return PlanningTransfer(
            destination=destination, content=content.strip(), retained_position_ids=retained_ids,
            uncertainties=[u.strip() for u in uncertainties if u.strip()],
            positions=[available[item] for item in retained_ids], discussion_digest=self.discussion_digest(state),
            context_digest=coverage.context_digest(state.presentation),
            coverage_digest=self._digest(state.presentation.evidence_coverage.model_dump(mode="json")),
            resources_digest=coverage.resources_digest(resources), passages_digest=coverage.passages_digest(state.resource_chunks),
            approved_by=actor,
        )

    def is_current(self, transfer, state):
        if not transfer or transfer.status != "approved" or state.presentation is None:
            return False
        coverage = EvidenceCoverageService()
        resources = self._selected(state)
        return (transfer.version == self.TRANSFER_VERSION
                and transfer.discussion_digest == self.discussion_digest(state)
                and transfer.context_digest == coverage.context_digest(state.presentation)
                and state.presentation.evidence_coverage is not None
                and transfer.coverage_digest == self._digest(state.presentation.evidence_coverage.model_dump(mode="json"))
                and transfer.resources_digest == coverage.resources_digest(resources)
                and transfer.passages_digest == coverage.passages_digest(state.resource_chunks))

    def planning_context(self, state):
        transfer = state.planning_transfer
        return transfer.model_dump(mode="json") if self.is_current(transfer, state) else None

    def discussion_digest(self, state):
        return self._digest([turn.model_dump(mode="json") for turn in state.resource_conversation_history])

    @classmethod
    def _signature(cls, text):
        return cls._space.sub(" ", cls._negation.sub("", text).casefold()).strip()

    @classmethod
    def _digest(cls, value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

    @staticmethod
    def _selected(state):
        selected = {r.id for r in state.presentation.resources}
        return [r for r in state.resource_library if r.id in selected and r.is_validated]

    @classmethod
    def _position(cls, citation, resources):
        resource = next(r for r in resources if r.id == citation.resource_id)
        extensions = resource.metadata.extensions
        date = resource.metadata.scientific_date.value if resource.metadata.scientific_date else None
        uncertainty = ("Scientific interpretation and superiority require human review."
                       if date else "Reliable scientific date is unavailable; human review is required.")
        return DiscussionPosition(
            id=hashlib.sha256(f"{resource.id}:{citation.page}:{citation.evidence_excerpt}".encode()).hexdigest()[:20],
            resource_id=resource.id, resource_title=resource.title or resource.filename,
            scientific_date=date, location_kind="slide" if resource.file_type.value == "pptx" else "page",
            location_number=citation.page, section=extensions.get("section"), exact_passage=citation.evidence_excerpt,
            doi=extensions.get("doi"), url=extensions.get("url"), uncertainty=uncertainty,
        )
