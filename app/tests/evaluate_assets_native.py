"""Opt-in 05.2 native synthetic probes; no model, downloads or source files."""
import hashlib
import base64
import json

import fitz

from app.application.services.raster_evaluation import fixture, XMP
from app.application.services.source_document import SourceDocument
from app.application.services.source_assets import asset_content
from app.tests.test_source_assets import table_pdf
from app.tests.evaluate_pptx_native import evaluate as pptx_evaluate


def evaluate():
    results = pptx_evaluate()
    png = fixture('Synthetic teaching evidence\nPublication date: 2024')
    with fitz.open() as doc:
        page = doc.new_page(width=500, height=300)
        page.insert_image(page.rect, stream=png)
        doc.set_xml_metadata(XMP)
        scan = doc.tobytes()
    results['pdf_assets'] = []
    for label, content in [('image', scan), ('table', table_pdf())]:
        source = SourceDocument.read('synthetic.pdf', content, 'native-assets')
        asset, = source.metadata.assets
        assert asset.kind == label
        assert asset.sha256 == hashlib.sha256(base64.b64decode(asset.content_base64)).hexdigest()
        preview, media = asset_content(source, asset.id, original_region=True)
        assert preview.startswith(b'\x89PNG') and media == 'image/png'
        assert asset.review_status == 'pending' and not asset.evidence_eligible
        results['pdf_assets'].append({'kind': label, 'page': asset.location.number,
                                      'hash_verified': True, 'original_region_rendered': True})
    results['limit'] = 'Five synthetic probes; no anonymisation, visual fidelity, detector accuracy or scientific-validity guarantee.'
    return results


if __name__ == '__main__':
    print(json.dumps(evaluate(), indent=2))
