"""Real native 04.2 evaluation. No providers, downloads or raw fixture files.

Run outside a containing sandbox that forbids macOS sandbox_apply:
  venv/bin/python -m app.application.services.raster_evaluation
An unavailable native engine is an error, never a skipped/passed OCR trial.
"""
from io import BytesIO
import json
from time import perf_counter

import fitz
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

from app.application.services.local_image_screening import LocalImageScreening
from app.application.services.raster_privacy import screen_raster_text, require_text_only_pixels
from app.application.services.source_document import SourceDocument
from app.application.services.source_date_policy import SourceDatePolicy
from app.domain.exceptions.workflow_error import WorkflowError

XMP = '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/"><prism:publicationDate>2024</prism:publicationDate></rdf:Description></rdf:RDF></x:xmpmeta>'


def fixture(text, *, fmt='PNG', metadata=False, face=False):
    image = Image.new('RGB', (1000, 600), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 40)
    draw.text((30, 30), text, font=font, fill='black')
    if face:
        draw.ellipse((100, 220, 400, 520), outline='black', width=4)
        draw.ellipse((170, 300, 190, 320), fill='black')
        draw.ellipse((310, 300, 330, 320), fill='black')
        draw.arc((170, 350, 330, 460), 0, 180, fill='black', width=4)
    output = BytesIO()
    info = PngImagePlugin.PngInfo()
    if metadata:
        info.add_text('XML:com.adobe.xmp', XMP)
    image.save(output, format=fmt, **({'pnginfo': info} if fmt == 'PNG' else {'quality': 100, 'subsampling': 0, **({'xmp': XMP.encode()} if metadata else {})}))
    return output.getvalue()


def evaluate():
    results = []
    for identifier, text, risky, face in [
        ('teaching', 'Synthetic teaching evidence\nPublication date: 2024', False, False),
        ('name', 'Name: Alice Example', True, False),
        ('email', 'alice@example.invalid', True, False),
        ('unlabelled_name', 'Alice Example', True, False),
        ('schematic_face', 'Synthetic teaching evidence', True, True),
    ]:
        started = perf_counter()
        png = fixture(text, face=face)
        result = LocalImageScreening.inspect_experimental(png)
        try:
            screen_raster_text('\n'.join(line.text for line in result.lines))
            require_text_only_pixels(png, result.lines)
            blocked = bool(result.faces)
        except WorkflowError:
            blocked = True
        results.append({'fixture': identifier, 'risk': risky, 'blocked': blocked, 'faces': result.faces,
                        'line_count': len(result.lines), 'min_confidence': min(line.confidence for line in result.lines),
                        'duration_ms': round((perf_counter() - started) * 1000)})
    imports = []
    for kind in ('png', 'jpeg', 'pdf'):
        content = fixture('Synthetic teaching evidence\nPublication date: 2024', fmt='JPEG' if kind == 'jpeg' else 'PNG', metadata=True)
        if kind == 'pdf':
            with fitz.open() as doc:
                page = doc.new_page(width=500, height=300)
                page.insert_image(page.rect, stream=content)
                doc.set_xml_metadata(XMP)
                content = doc.tobytes()
        print('Evaluating synthetic import: ' + kind, flush=True)
        source = SourceDocument.read('synthetic.' + kind, content, 'synthetic')
        assert source._original_content == content
        assert source.metadata.scientific_date.origin == 'scientific_metadata'
        assert source.metadata.ocr_regions and not source.is_validated
        SourceDocument.verify(source, content)
        try:
            SourceDatePolicy.require(source)
            raise AssertionError('Unconfirmed OCR reached scientific use')
        except WorkflowError as error:
            assert error.code == 'OCR_CONFIRMATION_REQUIRED'
        imports.append({'format': kind, 'original_verified': True, 'regions': len(source.metadata.ocr_regions), 'generation_blocked': True})
    return {'engine': LocalImageScreening.ENGINE, 'real_engine': True, 'fixtures': results, 'imports': imports,
            'note': 'Synthetic limited sample; no face-detection sensitivity or anonymisation guarantee.'}


if __name__ == '__main__':
    print(json.dumps(evaluate(), indent=2))
