"""Synthetic-only failure/bypass tests. OCR and face results use explicit doubles."""
import json
from io import BytesIO
import subprocess

import pytest
from PIL import Image, PngImagePlugin

from app.tests import test_raster_sources as raster_fixtures
from app.tests.test_raster_sources import synthetic_image, synthetic_scan
from app.tests import test_source_lifecycle as lifecycle
from app.tests.test_source_lifecycle import snapshot
from app.application.services.local_image_screening import LocalImageScreening
from app.application.services.raster_document import RasterDocument
from app.application.services.source_document import SourceDocument
from app.application.services.source_date_policy import SourceDatePolicy
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.source_metadata import OcrRegion


engine_double = raster_fixtures.engine_double
workspace = lifecycle.workspace


@pytest.mark.parametrize('kind', ['png', 'jpeg', 'pdf'])
def test_api_doubled_import_download_ownership_audit_and_delete(workspace, engine_double, kind):
    client, repository = workspace
    content = synthetic_scan() if kind == 'pdf' else synthetic_image(kind.upper())
    response = client.post('/resources/synthetic-owner/demo', files={'file': ('synthetic.' + kind, content)})
    assert response.status_code == 200, response.text
    identifier = response.json()['resource_id']
    state = client.get('/projects/synthetic-owner/demo').json()
    source = state['resource_library'][0]
    assert source['ocr_pending'] and source['ocr_region_count'] == 2
    assert source['source_blocker']['code'] == 'OCR_CONFIRMATION_REQUIRED'
    response = client.get(f'/projects/synthetic-owner/demo/resources/{identifier}/original')
    assert response.status_code == 200 and response.content == content
    assert response.headers['content-type'] == ('application/pdf' if kind == 'pdf' else 'image/' + kind)
    assert response.headers['cache-control'] == 'no-store'
    assert client.get(f'/projects/other/demo/resources/{identifier}/original').status_code == 403
    event = next(e for e in repository.list_events('synthetic-owner', 'demo') if e['event_type'] == 'RESOURCE_UPLOADED')
    assert event['payload']['ocr_pending'] is True
    assert 'Synthetic teaching' not in json.dumps(event)
    assert client.delete(f'/users/synthetic-owner/resources/{identifier}').status_code == 200
    assert client.get(f'/projects/synthetic-owner/demo/resources/{identifier}/original').status_code == 404


@pytest.mark.parametrize('failure', ['face', 'identifier', 'empty', 'date', 'uncertain_date', 'unavailable', 'timeout', 'interrupted'])
def test_no_raw_storage_or_logs_after_refusal(workspace, engine_double, monkeypatch, caplog, failure):
    client, repository = workspace
    if failure == 'face':
        engine_double.faces = 1
    elif failure == 'identifier':
        engine_double.lines[0].text = 'alice@example.invalid'
    elif failure == 'empty':
        engine_double.lines = []
    elif failure == 'date':
        engine_double.lines = engine_double.lines[:1]
    elif failure == 'uncertain_date':
        engine_double.lines[1].confidence = 0.5
    else:
        def fail(content):
            raise {'unavailable': RuntimeError, 'timeout': TimeoutError, 'interrupted': InterruptedError}[failure]('alice@example.invalid')
        monkeypatch.setattr(LocalImageScreening, 'inspect', fail)
    before = snapshot(repository)
    files = set(repository.database_path.parent.rglob('*'))
    response = client.post('/resources/synthetic-owner/demo', files={'file': ('synthetic.png', synthetic_image())})
    assert response.status_code == 422, response.text
    assert snapshot(repository) == before
    assert set(repository.database_path.parent.rglob('*')) == files
    assert 'alice@example.invalid' not in response.text + caplog.text


def test_low_confidence_ocr_date_requires_independent_scientific_metadata(engine_double):
    engine_double.lines[1].confidence = 0.5
    source = SourceDocument.read('synthetic.png', synthetic_image(metadata=True), 'synthetic')
    assert source.metadata.scientific_date.origin == 'scientific_metadata'
    with pytest.raises(WorkflowError, match='unconfirmed'):
        SourceDatePolicy.require(source)


@pytest.mark.parametrize('key,value', [('Author', 'Alice Example'), ('Description', 'alice@example.invalid'), ('GPS', 'alice@example.invalid'), ('exif', b'opaque'), ('icc_profile', b'opaque')])
def test_image_metadata_cannot_be_stripped_to_bypass_screening(engine_double, key, value):
    image = Image.new('RGB', (100, 100), 'white')
    output = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    kwargs = {}
    if isinstance(value, str):
        metadata.add_text(key, value)
    else:
        kwargs[key] = value
    image.save(output, format='PNG', pnginfo=metadata, **kwargs)
    with pytest.raises(WorkflowError):
        SourceDocument.read('synthetic.png', output.getvalue(), 'synthetic')


@pytest.mark.parametrize('box', [[0.2, 0, 0.1, 1], [0, 0, 2, 1], [0, 0, float('nan'), 1]])
def test_invalid_original_region(box):
    with pytest.raises(ValueError):
        OcrRegion(text='Synthetic', box=box, confidence=0.9)


@pytest.mark.parametrize('field', ['text', 'box', 'confidence', 'date', 'flag'])
def test_direct_forged_extraction_refused(engine_double, field):
    source = SourceDocument.read('synthetic.png', synthetic_image(), 'synthetic')
    if field == 'text':
        source.metadata.ocr_regions[0].text = 'Forged content'
    elif field == 'box':
        source.metadata.ocr_regions[0].box = (0.2, 0.2, 0.4, 0.4)
    elif field == 'confidence':
        source.metadata.ocr_regions[0].confidence = 1
    elif field == 'date':
        source.metadata.scientific_date.value = '2023'
    else:
        source.is_validated = True
    from app.application.services.source_screening import SourceScreening
    with pytest.raises(WorkflowError):
        SourceScreening.resource(source)
        SourceDocument.verify(source, source._original_content)


def test_input_and_total_time_limits(engine_double, monkeypatch):
    monkeypatch.setattr(LocalImageScreening, 'MAX_PIXELS', 100)
    with pytest.raises(WorkflowError):
        SourceDocument.read('synthetic.png', synthetic_image(), 'synthetic')
    monkeypatch.setattr(LocalImageScreening, 'MAX_PIXELS', 16_000_000)
    monkeypatch.setattr(RasterDocument, 'MAX_SECONDS', -1)
    with pytest.raises(WorkflowError):
        SourceDocument.read('synthetic.png', synthetic_image(), 'synthetic')


def test_native_wrapper_enforces_sandbox_timeout_and_hides_errors(monkeypatch, tmp_path):
    binary = tmp_path / 'engine'
    binary.touch()
    monkeypatch.setattr(LocalImageScreening, 'BINARY', binary)
    monkeypatch.setattr('app.application.services.local_image_screening.sys.platform', 'darwin')
    def timeout(command, **kwargs):
        assert command[:2] == ['/usr/bin/sandbox-exec', '-p']
        assert '(deny file-write*)' in command[2] and '(deny network*)' in command[2]
        assert kwargs['input'] == b'synthetic' and kwargs['stderr'] == subprocess.DEVNULL
        assert kwargs['timeout'] == 30
        raise subprocess.TimeoutExpired(command, 30, stderr=b'alice@example.invalid')
    monkeypatch.setattr(subprocess, 'run', timeout)
    with pytest.raises(WorkflowError) as error:
        LocalImageScreening.inspect_experimental(b'synthetic')
    assert 'alice' not in str(error.value)


@pytest.mark.parametrize('kind', ['png', 'jpeg', 'pdf'])
def test_unavailable_native_engine_never_unlocks_production_import(workspace, kind, monkeypatch):
    client, repository = workspace
    monkeypatch.setattr(LocalImageScreening, 'BINARY', repository.database_path.parent / 'missing-engine')
    before = snapshot(repository)
    content = synthetic_scan() if kind == 'pdf' else synthetic_image(kind.upper())
    response = client.post('/resources/synthetic-owner/demo', files={'file': ('synthetic.' + kind, content)})
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'SOURCE_SCREENING_INCOMPLETE'
    assert snapshot(repository) == before


def test_pending_ocr_cannot_reach_direct_evidence_builder_or_agent(engine_double, monkeypatch):
    from app.ai.prompt_builders.evidence_context_builder import EvidenceContextBuilder
    from app.application.services.ocr_evidence_gate import require_confirmed_ocr
    from app.ai.agents.healthcare_presentation_agent import HealthcarePresentationAgent
    from app.ai.workflows.graph_state import GraphState
    source = SourceDocument.read('synthetic.png', synthetic_image(), 'synthetic')
    for call in [lambda: EvidenceContextBuilder().for_overview([source]),
                 lambda: require_confirmed_ocr([source]),
                 lambda: HealthcarePresentationAgent.__new__(HealthcarePresentationAgent).invoke(
                     GraphState(prototype_declaration='synthetic', resource_library=[source]), 'synthetic')]:
        with pytest.raises(WorkflowError) as error:
            call()
        assert error.value.code == 'OCR_CONFIRMATION_REQUIRED'
