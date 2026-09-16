"""Opt-in real native synthetic PPTX evaluation; no providers or fixture files.

Run: venv/bin/python -m app.tests.evaluate_pptx_native
Native sandbox-exec needs an environment permitting macOS sandbox_apply.
"""
import json

from app.application.services.raster_evaluation import fixture
from app.application.services.source_document import SourceDocument
from app.domain.exceptions.workflow_error import WorkflowError
from app.tests.test_pptx_sources import deck


def evaluate():
    results = []
    for label, text, face in (
        ('teaching', 'Synthetic teaching evidence', False),
        ('name', 'Alice Example', False),
        ('schematic_face', 'Synthetic teaching evidence', True),
    ):
        content = deck(image=fixture(text, face=face))
        try:
            source = SourceDocument.read('synthetic.pptx', content, 'native-synthetic')
        except WorkflowError as error:
            if label == 'teaching':
                raise
            results.append({'fixture': label, 'refused': True, 'code': error.code})
        else:
            assert label == 'teaching', 'A risky synthetic fixture was accepted'
            assert [asset.kind for asset in source.metadata.assets] == ['table', 'image']
            assert source.metadata.assets[1].location.number == 2
            assert not source.metadata.ocr_regions
            assert 'Synthetic teaching evidence' not in source.extracted_text
            SourceDocument.verify(source, content)
            results.append({'fixture': label, 'original_verified': True, 'image_slide': 2, 'ocr_used_as_evidence': False})
    return {'real_native_engine': True, 'results': results,
            'limit': 'Three synthetic fixtures; no anonymisation or face-detection accuracy claim.'}


if __name__ == '__main__':
    print(json.dumps(evaluate(), indent=2))
