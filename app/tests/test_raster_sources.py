"""04.2 synthetic sources; deterministic engine doubles are explicitly labelled."""
from io import BytesIO

import fitz
import pytest
from PIL import Image, PngImagePlugin

from app.application.services.local_image_screening import ImageInspection, LocalImageScreening
from app.application.services.source_document import SourceDocument
from app.application.services.source_date_policy import SourceDatePolicy
from app.domain.exceptions.workflow_error import WorkflowError
from app.ai.workflows.graph_state import GraphState
from app.interfaces.storage.user_session_repository import UserSessionRepository

XMP = '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/"><prism:publicationDate>2024</prism:publicationDate></rdf:Description></rdf:RDF></x:xmpmeta>'


def synthetic_image(fmt='PNG', metadata=False):
    image = Image.new('RGB', (300, 200), 'white')
    output = BytesIO()
    info = PngImagePlugin.PngInfo()
    if metadata:
        info.add_text('XML:com.adobe.xmp', XMP)
    image.save(output, format=fmt, **({'pnginfo': info} if fmt == 'PNG' else {}))
    return output.getvalue()


def synthetic_scan(metadata=False):
    with fitz.open() as doc:
        page = doc.new_page(width=300, height=200)
        page.insert_image(page.rect, stream=synthetic_image())
        if metadata:
            doc.set_xml_metadata(XMP)
        return doc.tobytes()


@pytest.fixture
def engine_double(monkeypatch):
    result = ImageInspection(lines=[
        {'text': 'Synthetic teaching evidence', 'box': [0.1, 0.1, 0.9, 0.2], 'confidence': 0.99},
        {'text': 'Publication date: 2024', 'box': [0.1, 0.3, 0.9, 0.4], 'confidence': 0.99},
    ], faces=0)
    monkeypatch.setattr(LocalImageScreening, 'inspect', lambda content: result.model_copy(deep=True))
    return result


@pytest.mark.parametrize('kind', ['png', 'jpeg', 'pdf'])
def test_doubled_engine_original_regions_restart_and_pending_generation(tmp_path, engine_double, kind):
    content = synthetic_scan() if kind == 'pdf' else synthetic_image(kind.upper())
    source = SourceDocument.read('synthetic.' + kind, content, 'synthetic')
    assert source.file_type.value == kind
    assert source.metadata.ocr_regions[0].box == (0.1, 0.1, 0.9, 0.2)
    assert source.metadata.scientific_date.origin == 'ocr_text'
    assert not source.is_validated
    repository = UserSessionRepository(tmp_path / 'raster.sqlite3')
    repository.save('owner', 'demo', 'thread', GraphState(resource_library=[source]))
    reopened = UserSessionRepository(repository.database_path)
    source = reopened.load('owner', 'demo')[1].resource_library[0]
    assert source._original_content == content
    assert source.metadata.ocr_regions[0].uncertain is True
    assert SourceDocument.verify(source, content) == content
    with pytest.raises(WorkflowError) as error:
        SourceDatePolicy.require(source)
    assert error.value.code == 'OCR_CONFIRMATION_REQUIRED'
    reopened.permanently_delete_source('owner', 'synthetic', 'owner')
    assert UserSessionRepository(repository.database_path).list_library_resources('owner') == []
