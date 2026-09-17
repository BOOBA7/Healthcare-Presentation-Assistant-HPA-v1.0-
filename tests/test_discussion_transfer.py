"""Behavioural tests for neutral conflicts and explicit planning transfer (06.3)."""

import pytest

from app.ai.workflows.graph_state import GraphState
from app.application.services.conversation_history import add_resource_turn
from app.application.services.discussion_transfer import DiscussionTransferService
from app.application.use_cases.create_presentation import CreatePresentationUseCase
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.exceptions.concurrent_modification_error import ConcurrentModificationError
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.conversation_turn import ConversationTurn
from app.domain.value_objects.presentation_context import PresentationContext
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.tests.source_fixtures import dated_resource


POSITIVE = "Controller therapy is recommended for adults."
NEGATIVE = "Controller therapy is not recommended for adults."


def _context():
    return PresentationContext(
        topic="Asthma controller therapy", audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE, language=Language.ENGLISH,
        duration_minutes=20, objective="Compare asthma controller therapy",
        target_slide_count=6, special_instructions="Advanced specialist review",
        professional_scope="specialist teaching", is_multidisciplinary=False,
    )


def _resources(second=NEGATIVE):
    common = "Advanced specialist review compares asthma controller therapy for adults in detailed clinical teaching. "
    return [
        dated_resource(id="r1", filename="one.pdf", title="Position One", is_validated=True,
                       extracted_pages=[{"page": 2, "text": common + POSITIVE}]),
        dated_resource(id="r2", filename="two.pdf", title="Position Two", is_validated=True,
                       extracted_pages=[{"page": 3, "text": common + second}]),
    ]


def _answer(second=NEGATIVE):
    return (f"Two passages require comparison [[cite: r1 | p. 2 | {POSITIVE}]] "
            f"and [[cite: r2 | p. 3 | {second}]].")


def _repository(tmp_path):
    resources = _resources()
    presentation = CreatePresentationUseCase().execute("Asthma controller therapy", _context())
    presentation.resources = [item.model_copy(deep=True) for item in resources]
    presentation.state.resources_validated = True
    state = GraphState(prototype_declaration="synthetic", resource_library=resources, presentation=presentation)
    repository = UserSessionRepository(tmp_path / "transfer.sqlite3")
    repository.save_with_event("owner", "project", "thread", state, "SETUP", "owner")
    _, state = repository.load("owner", "project")
    _, state = repository.assess_evidence_coverage("owner", "project", state.project_revision, "owner")
    add_resource_turn(state, "user", "Compare the recommendations")
    add_resource_turn(state, "assistant", _answer())
    repository.save_with_event("owner", "project", "thread", state, "DISCUSSION", "llm")
    return repository


def test_positions_preserve_provenance_and_limited_rule_does_not_rank_sources():
    history = [ConversationTurn(role="assistant", text=_answer())]
    comparison = DiscussionTransferService().comparisons(history, _resources())[0]
    assert comparison.classification == "deterministic_conflict"
    assert [position.resource_title for position in comparison.positions] == ["Position One", "Position Two"]
    assert [position.location_number for position in comparison.positions] == [2, 3]
    assert all(position.scientific_date == "2024" for position in comparison.positions)
    assert all(position.human_review_required for position in comparison.positions)
    assert "superior" not in comparison.rule.casefold()


def test_wording_or_population_difference_is_only_potential_conflict():
    other = "Controller therapy is recommended for selected adolescents."
    comparison = DiscussionTransferService().comparisons(
        [ConversationTurn(role="assistant", text=_answer(other))], _resources(other)
    )[0]
    assert comparison.classification == "potential_conflict"
    assert "human" in comparison.rule.casefold()


def test_explicit_transfer_is_atomic_durable_revisioned_and_does_not_create_planning_objects(tmp_path):
    repository = _repository(tmp_path)
    _, state = repository.load("owner", "project")
    state.resource_chunks = repository.load_resource_chunks("owner", "project")
    positions = DiscussionTransferService().comparisons(state.resource_conversation_history, state.resource_library)[0].positions
    _, approved = repository.approve_discussion_transfer(
        "owner", "project", state.project_revision, "agenda", "Retain both positions for review.",
        [position.id for position in positions], ["Applicability requires professor review."], "owner",
    )
    reopened = UserSessionRepository(repository.database_path).load("owner", "project")[1]
    assert reopened.planning_transfer.status == "approved"
    assert reopened.planning_transfer.approved_by == "owner"
    assert reopened.presentation.agenda is None
    assert reopened.presentation.blueprint is None
    assert approved.presentation.agenda is None


def test_partial_model_or_fabricated_transfer_and_stale_revision_are_refused(tmp_path):
    repository = _repository(tmp_path)
    _, state = repository.load("owner", "project")
    state.resource_chunks = repository.load_resource_chunks("owner", "project")
    positions = DiscussionTransferService().comparisons(state.resource_conversation_history, state.resource_library)[0].positions
    with pytest.raises(ValueError, match="retained together"):
        repository.approve_discussion_transfer("owner", "project", state.project_revision, "agenda", "One side", [positions[0].id], [], "owner")
    with pytest.raises(ConcurrentModificationError):
        repository.approve_discussion_transfer("owner", "project", state.project_revision - 1, "agenda", "Both", [p.id for p in positions], [], "owner")
    with pytest.raises(WorkflowError, match="authenticated Project owner"):
        repository.approve_discussion_transfer("owner", "project", state.project_revision, "agenda", "Both", [p.id for p in positions], [], "model")
    fabricated = state.model_copy(deep=True)
    fabricated.planning_transfer = DiscussionTransferService().create_transfer(
        state, "agenda", "Both", [p.id for p in positions], [], "model"
    )
    with pytest.raises(WorkflowError, match="authenticated discussion-transfer"):
        repository.save("owner", "project", "thread", fabricated)


def test_owner_isolation_audit_rollback_and_discussion_invalidation(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    _, state = repository.load("owner", "project")
    state.resource_chunks = repository.load_resource_chunks("owner", "project")
    positions = DiscussionTransferService().comparisons(state.resource_conversation_history, state.resource_library)[0].positions
    ids = [p.id for p in positions]
    with pytest.raises(WorkflowError, match="Project not found"):
        repository.approve_discussion_transfer("intruder", "project", state.project_revision, "agenda", "Both", ids, [], "intruder")
    original = repository._insert_event
    monkeypatch.setattr(repository, "_insert_event", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")))
    with pytest.raises(RuntimeError, match="audit unavailable"):
        repository.approve_discussion_transfer("owner", "project", state.project_revision, "agenda", "Both", ids, [], "owner")
    assert repository.load("owner", "project")[1].planning_transfer is None
    monkeypatch.setattr(repository, "_insert_event", original)
    _, approved = repository.approve_discussion_transfer("owner", "project", state.project_revision, "agenda", "Both", ids, [], "owner")
    add_resource_turn(approved, "user", "A changed follow-up question")
    repository.save("owner", "project", "thread", approved)
    assert repository.load("owner", "project")[1].planning_transfer.status == "obsolete"


def test_transfer_content_is_protected_and_context_change_makes_it_obsolete(tmp_path):
    repository = _repository(tmp_path)
    _, state = repository.load("owner", "project")
    state.resource_chunks = repository.load_resource_chunks("owner", "project")
    ids = [p.id for p in DiscussionTransferService().comparisons(
        state.resource_conversation_history, state.resource_library
    )[0].positions]
    _, approved = repository.approve_discussion_transfer(
        "owner", "project", state.project_revision, "blueprint", "Both positions", ids,
        ["Human interpretation required"], "owner",
    )
    altered = approved.model_copy(deep=True)
    altered.planning_transfer.content = "Silently changed content"
    with pytest.raises(WorkflowError, match="authenticated discussion-transfer"):
        repository.save("owner", "project", "thread", altered)
    approved.presentation.context.objective = "A changed learning objective"
    repository.save("owner", "project", "thread", approved)
    reopened = repository.load("owner", "project")[1]
    assert reopened.planning_transfer.status == "obsolete"
    assert reopened.presentation.evidence_coverage is None
