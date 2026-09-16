"""04.1 synthetic-only screening regression and evaluation evidence."""
import pytest
from langchain_core.messages import HumanMessage

from app.application.services.prototype_policy import PrototypePolicy
from app.ai.llm.llm import PrototypeProviderGuard
from app.domain.exceptions.workflow_error import WorkflowError


@pytest.mark.parametrize('text', [
    'Name: Alice Example', 'Nom: Alice Exemple', 'alice@example.invalid',
    'Telephone: +33 6 12 34 56 78', 'Record number: SYN12345',
    'Date of birth: 1990-01-02', '12 rue Exemple',
    'Age: 97; village: Syntheticville; occupation: baker',
])
def test_identifier_blocked_at_common_and_direct_provider_gate(text):
    with pytest.raises(WorkflowError):
        PrototypePolicy.screen(text)
    with pytest.raises(WorkflowError):
        PrototypeProviderGuard().on_chat_model_start({}, [[HumanMessage(content=text)]])


@pytest.mark.parametrize('text', ['Publication date: 2024-01-02', 'Synthetic teaching evidence', 'Mean age: 65'])
def test_non_identifying_teaching_text(text):
    PrototypePolicy.screen(text)


def test_multimodal_provider_bypass_is_incomplete():
    with pytest.raises(WorkflowError, match='screening'):
        PrototypeProviderGuard().on_chat_model_start({}, [[HumanMessage(content=[{'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,synthetic'}}])]])


def test_evaluation_counts_misses_without_claiming_ocr():
    from app.application.services.privacy_evaluation import evaluate
    result = evaluate()
    assert result['text'] == {'tp': 7, 'tn': 3, 'fp': 1, 'fn': 3}
    assert len(result['image_cases']) == 6
    assert all(case['gate'] == 'SOURCE_SCREENING_INCOMPLETE' for case in result['image_cases'])
    assert result['real_ocr_trials'] == result['face_detection_trials'] == 0


@pytest.mark.parametrize('surface', ['text', 'metadata', 'xml', 'filename'])
def test_refused_identifiers_leave_no_raw_storage_or_logs(tmp_path, caplog, surface):
    import fitz
    from app.application.services.source_document import SourceDocument
    from app.interfaces.storage.user_session_repository import UserSessionRepository
    from app.ai.workflows.graph_state import GraphState
    repository = UserSessionRepository(tmp_path / 'privacy.sqlite3')
    with repository._connect() as connection:
        before = '\n'.join(connection.iterdump())
    files = set(tmp_path.rglob('*'))
    raw = 'alice@example.invalid'
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 72), 'Publication date: 2024\n' + (raw if surface == 'text' else 'Teaching'))
        if surface == 'metadata':
            doc.set_metadata({'author': raw})
        if surface == 'xml':
            doc.set_xml_metadata('<metadata>' + raw + '</metadata>')
        content = doc.tobytes()
    with pytest.raises(WorkflowError) as error:
        resource = SourceDocument.read(raw if surface == 'filename' else 'synthetic.pdf', content, 'synthetic')
        repository.save('owner', 'demo', 'thread', GraphState(resource_library=[resource]))
    assert raw not in str(error.value) and raw not in caplog.text
    with repository._connect() as connection:
        assert '\n'.join(connection.iterdump()) == before
    assert set(tmp_path.rglob('*')) == files


@pytest.mark.parametrize('failure', [RuntimeError, TimeoutError, InterruptedError])
def test_failed_detector_refuses_direct_gate_without_raw_diagnostic(monkeypatch, failure):
    from app.application.services.identifier_screening import IdentifierScreening
    def fail(text):
        raise failure('alice@example.invalid')
    monkeypatch.setattr(IdentifierScreening, 'findings', fail)
    with pytest.raises(WorkflowError) as error:
        PrototypePolicy.screen('Synthetic teaching')
    assert error.value.code == 'SOURCE_SCREENING_INCOMPLETE'
    assert 'alice' not in str(error.value)


def test_text_limit_refuses(monkeypatch):
    from app.application.services.identifier_screening import IdentifierScreening
    monkeypatch.setattr(IdentifierScreening, 'MAX_CHARS', 5)
    with pytest.raises(WorkflowError) as error:
        PrototypePolicy.screen('Synthetic teaching')
    assert error.value.code == 'SOURCE_SCREENING_INCOMPLETE'


@pytest.mark.parametrize('entry', ['save', 'sync', 'library'])
def test_new_identifier_direct_repository_bypass(tmp_path, entry):
    from app.tests.source_fixtures import dated_resource
    from app.interfaces.storage.user_session_repository import UserSessionRepository
    from app.ai.workflows.graph_state import GraphState
    repository = UserSessionRepository(tmp_path / 'privacy.sqlite3')
    resource = dated_resource(id='synthetic', filename='synthetic.pdf')
    resource.metadata.extensions['untrusted'] = 'Name: Alice Example'
    with repository._connect() as connection:
        before = '\n'.join(connection.iterdump())
        with pytest.raises(WorkflowError):
            if entry == 'save':
                repository.save('owner', 'demo', 'thread', GraphState(resource_library=[resource]))
            elif entry == 'sync':
                repository._sync_resources(connection, 'owner', 'demo', [resource])
            else:
                repository._remember_source(connection, 'owner', resource)
        assert connection.total_changes == 0
        assert '\n'.join(connection.iterdump()) == before
