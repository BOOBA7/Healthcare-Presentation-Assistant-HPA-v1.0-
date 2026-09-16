"""04.3 authenticated review, exact originals and transactional provenance."""
import pytest

from app.tests import test_raster_sources as fixtures
from app.application.services.source_document import SourceDocument
from app.application.services.source_date_policy import SourceDatePolicy
from app.ai.workflows.graph_state import GraphState
from app.interfaces.storage.user_session_repository import UserSessionRepository

engine_double = fixtures.engine_double


def test_review_survives_restart_and_updates_evidence(tmp_path, engine_double):
    repository = UserSessionRepository(tmp_path / 'review.sqlite3')
    source = SourceDocument.read('synthetic.png', fixtures.synthetic_image(), 'synthetic')
    repository.save('owner', 'demo', 'thread', GraphState(resource_library=[source]))
    repository.review_ocr('owner', 'synthetic', 0,
                          ['Synthetic corrected teaching evidence', 'Publication date: 2024'], [0, 1])
    reopened = UserSessionRepository(repository.database_path)
    reviewed = reopened.load('owner', 'demo')[1].resource_library[0]
    assert reviewed.extracted_pages[0]['text'].startswith('Synthetic corrected')
    assert reviewed.metadata.ocr_regions[0].text == 'Synthetic teaching evidence'
    assert reviewed.metadata.ocr_reviews[0].actor == 'owner'
    assert reviewed.metadata.ocr_reviews[0].provenance == 'user_confirmed'
    assert reviewed.metadata.ocr_reviews[0].confirmed_at.tzinfo is not None
    assert SourceDatePolicy.require(reviewed).origin == 'user_confirmed'
    assert reviewed._original_content == source._original_content
    assert reviewed.is_validated


@pytest.mark.parametrize('fault', ['partial', 'duplicate', 'identifier', 'stale', 'date'])
def test_review_rejections_are_atomic(tmp_path, engine_double, fault):
    from app.domain.exceptions.workflow_error import WorkflowError
    from app.tests.test_source_lifecycle import snapshot
    repository = UserSessionRepository(tmp_path / 'review.sqlite3')
    source = SourceDocument.read('synthetic.png', fixtures.synthetic_image(), 'synthetic')
    repository.save('owner', 'demo', 'thread', GraphState(resource_library=[source]))
    before = snapshot(repository)
    values = ['Synthetic corrected teaching evidence', 'Publication date: 2024']
    confirmed = [0, 1]
    revision = 0
    if fault == 'partial':
        confirmed = [0]
    elif fault == 'duplicate':
        confirmed = [0, 0]
    elif fault == 'identifier':
        values[0] = 'alice@example.invalid'
    elif fault == 'stale':
        revision = 1
    else:
        values[1] = 'No publication date'
    with pytest.raises(WorkflowError):
        repository.review_ocr('owner', 'synthetic', revision, values, confirmed)
    assert snapshot(repository) == before


def test_forged_review_and_tampered_confirmed_value_blocked(tmp_path, engine_double):
    from app.domain.exceptions.workflow_error import WorkflowError
    from app.application.services.ocr_review import is_reviewed
    repository = UserSessionRepository(tmp_path / 'review.sqlite3')
    source = SourceDocument.read('synthetic.png', fixtures.synthetic_image(), 'synthetic')
    repository.save('owner', 'demo', 'thread', GraphState(resource_library=[source]))
    repository.review_ocr('owner', 'synthetic', 0, ['Synthetic corrected teaching evidence', 'Publication date: 2024'], [0, 1])
    thread, state = repository.load('owner', 'demo')
    resource = state.resource_library[0]
    assert is_reviewed(resource)
    resource.metadata.ocr_reviews[0].corrected_value = 'Forged evidence'
    assert not is_reviewed(resource)
    with pytest.raises(WorkflowError):
        repository.save('owner', 'demo', thread, state)
    with pytest.raises(WorkflowError):
        SourceDatePolicy.require(resource)


def test_review_invalidates_all_projects_and_audit_failure_rolls_back(tmp_path, engine_double, monkeypatch):
    from app.tests.test_source_lifecycle import snapshot
    from app.domain.models.resource_analysis import ResourceAnalysis
    repository = UserSessionRepository(tmp_path / 'review.sqlite3')
    source = SourceDocument.read('synthetic.png', fixtures.synthetic_image(), 'synthetic')
    for project in ('one', 'two'):
        repository.save('owner', project, 'thread', GraphState(resource_library=[source], resource_analysis=ResourceAnalysis(summary='Stale synthetic summary', resource_ids=['synthetic'])))
    before = snapshot(repository)
    original = repository._insert_event
    def fail(*args):
        raise RuntimeError('Synthetic audit fault')
    monkeypatch.setattr(repository, '_insert_event', fail)
    with pytest.raises(RuntimeError):
        repository.review_ocr('owner', 'synthetic', 0, ['Synthetic corrected evidence', 'Publication date: 2024'], [0, 1])
    assert snapshot(repository) == before
    monkeypatch.setattr(repository, '_insert_event', original)
    repository.review_ocr('owner', 'synthetic', 0, ['Synthetic corrected evidence', 'Publication date: 2024'], [0, 1])
    for project in ('one', 'two'):
        state = repository.load('owner', project)[1]
        assert state.resource_analysis is None
        assert state.resource_library[0].metadata.ocr_reviews
    repository.permanently_delete_source('owner', 'synthetic', 'owner')
    assert 'Synthetic corrected evidence' not in snapshot(repository)


from app.tests import test_source_lifecycle as lifecycle  # noqa: E402
workspace = lifecycle.workspace


def test_authenticated_review_api_regions_and_corrected_retrieval(workspace, engine_double):
    from PIL import Image
    from io import BytesIO
    from app.ai.prompt_builders.evidence_context_builder import EvidenceContextBuilder
    client, repository = workspace
    response = client.post('/resources/synthetic-owner/demo', files={'file': ('synthetic.png', fixtures.synthetic_image())})
    identifier = response.json()['resource_id']
    path = f'/users/synthetic-owner/resources/{identifier}'
    form = client.get(path + '/ocr-review')
    assert form.status_code == 200 and form.headers['cache-control'] == 'no-store'
    assert form.json()['revision'] == 0
    preview = client.get(path + '/ocr-regions/0')
    assert preview.status_code == 200 and preview.headers['cache-control'] == 'no-store'
    with Image.open(BytesIO(preview.content)) as crop:
        assert crop.size == (240, 20)
    assert client.get(f'/users/other/resources/{identifier}/ocr-review').status_code == 403
    request = {'expected_revision': 0, 'values': ['Synthetic corrected teaching evidence', 'Publication date: 2024'], 'confirmed_regions': [0, 1]}
    assert client.post(path + '/ocr-review', json={**request, 'actor': 'forged'}).status_code == 422
    assert client.post(path + '/ocr-review', json=request).status_code == 200
    assert client.post(path + '/ocr-review', json=request).status_code == 409
    resource = repository.load('synthetic-owner', 'demo')[1].resource_library[0]
    context = EvidenceContextBuilder().for_overview([resource], repository.load_resource_chunks('synthetic-owner', 'demo'))
    assert 'Synthetic corrected teaching evidence' in context
    assert 'Synthetic teaching evidence' not in context
    assert client.get(path + '/ocr-review').json()['regions'][0]['review']['actor'] == 'synthetic-owner'


def test_review_history_is_append_only_and_direct_json_has_no_receipt(tmp_path, engine_double):
    from app.application.services.ocr_review import is_reviewed
    from app.domain.models.resource import Resource
    from app.domain.exceptions.workflow_error import WorkflowError
    repository = UserSessionRepository(tmp_path / 'review.sqlite3')
    source = SourceDocument.read('synthetic.png', fixtures.synthetic_image(), 'synthetic')
    repository.save('owner', 'demo', 'thread', GraphState(resource_library=[source]))
    repository.review_ocr('owner', 'synthetic', 0, ['First corrected teaching evidence', 'Publication date: 2024'], [0, 1])
    repository.review_ocr('owner', 'synthetic', 1, ['Second corrected teaching evidence', 'Publication date: 2024'], [0, 1])
    reviewed = repository.library_resource('owner', 'synthetic')
    assert [r.batch for r in reviewed.metadata.ocr_reviews] == [1, 1, 2, 2]
    restored_from_json = Resource.model_validate_json(reviewed.model_dump_json())
    restored_from_json._original_content = reviewed._original_content
    assert not is_reviewed(restored_from_json)
    with pytest.raises(WorkflowError):
        SourceDatePolicy.require(restored_from_json)


def test_rejected_review_api_never_echoes_raw_input(workspace, caplog):
    client, repository = workspace
    from app.tests.test_source_lifecycle import snapshot
    before = snapshot(repository)
    response = client.post('/users/synthetic-owner/resources/missing/ocr-review', json={
        'expected_revision': 'alice@example.invalid', 'values': ['alice@example.invalid'], 'confirmed_regions': []})
    assert response.status_code == 422
    assert 'alice' not in response.text + caplog.text
    assert snapshot(repository) == before


def test_confirmed_content_provenance_and_stale_project_save(tmp_path, engine_double):
    from app.application.services.citation_presentation import format_citations_for_display
    from app.ai.prompt_builders.evidence_context_builder import EvidenceContextBuilder
    from app.domain.exceptions.workflow_error import WorkflowError
    from app.domain.exceptions.concurrent_modification_error import ConcurrentModificationError
    repository = UserSessionRepository(tmp_path / 'review.sqlite3')
    source = SourceDocument.read('synthetic.png', fixtures.synthetic_image(), 'synthetic')
    repository.save('owner', 'demo', 'thread', GraphState(resource_library=[source]))
    thread, stale = repository.load('owner', 'demo')
    repository.review_ocr('owner', 'synthetic', 0, ['Synthetic corrected teaching evidence', 'Publication date: 2024'], [0, 1])
    with pytest.raises((WorkflowError, ConcurrentModificationError)):
        repository.save('owner', 'demo', thread, stale)
    current = repository.library_resource('owner', 'synthetic')
    assert 'PROVENANCE: user_confirmed' in EvidenceContextBuilder().for_overview([current])
    assert 'user_confirmed' in format_citations_for_display('[[cite: synthetic | p. 1 | Synthetic corrected teaching evidence]]', [current])


def test_numeric_correction_preserves_extracted_value_and_original_region(tmp_path, engine_double):
    engine_double.lines[0].text = 'Synthetic measurement: 25'
    repository = UserSessionRepository(tmp_path / 'review.sqlite3')
    source = SourceDocument.read('synthetic.png', fixtures.synthetic_image(), 'synthetic')
    repository.save('owner', 'demo', 'thread', GraphState(resource_library=[source]))
    repository.review_ocr('owner', 'synthetic', 0, ['Synthetic measurement: 2.5', 'Publication date: 2024'], [0, 1])
    updated = UserSessionRepository(repository.database_path).library_resource('owner', 'synthetic')
    review = updated.metadata.ocr_reviews[0]
    assert review.original_value == 'Synthetic measurement: 25'
    assert review.corrected_value == 'Synthetic measurement: 2.5'
    assert updated.metadata.ocr_regions[0].box == source.metadata.ocr_regions[0].box
    assert 'Synthetic measurement: 2.5' in updated.extracted_text


def test_delete_remains_available_when_ocr_engine_is_offline(tmp_path, engine_double, monkeypatch):
    from app.application.services.local_image_screening import LocalImageScreening
    repository = UserSessionRepository(tmp_path / 'review.sqlite3')
    sources = [SourceDocument.read('synthetic.png', fixtures.synthetic_image(), identifier) for identifier in ('first', 'second')]
    repository.save('owner', 'demo', 'thread', GraphState(resource_library=sources))
    repository.review_ocr('owner', 'second', 0, ['Synthetic reviewed teaching evidence', 'Publication date: 2024'], [0, 1])
    def unavailable(content):
        raise RuntimeError('OCR unavailable')
    monkeypatch.setattr(LocalImageScreening, 'inspect', unavailable)
    repository.permanently_delete_source('owner', 'first', 'owner')
    reopened = UserSessionRepository(repository.database_path)
    assert [source.id for source in reopened.list_library_resources('owner')] == ['second']
    assert reopened.load('owner', 'demo')[1].resource_library[0].metadata.ocr_reviews
