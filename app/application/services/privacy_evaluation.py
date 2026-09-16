"""Run with python -m app.application.services.privacy_evaluation. Synthetic only.

Reports fixture IDs and counts, never source text. Does not load/download OCR
models, invoke providers, write images, or enable imports.
"""
import importlib.util
import json
import shutil
from io import BytesIO

import fitz
from PIL import Image, ImageDraw

from app.application.services.prototype_policy import PrototypePolicy
from app.application.services.source_screening import SourceScreening
from app.domain.exceptions.workflow_error import WorkflowError

# Ground truth is deliberately independent of detector results. Known misses and
# overblocking remain visible rather than being relabelled to make metrics pass.
CASES = [
    ('labelled_name', True, 'Name: Alice Example'),
    ('email', True, 'alice@example.invalid'),
    ('phone', True, 'Telephone: +33 6 12 34 56 78'),
    ('record', True, 'Record number: SYN12345'),
    ('birth', True, 'Date of birth: 1990-01-02'),
    ('address', True, '12 rue Exemple'),
    ('combination', True, 'Age: 97; village: Syntheticville; occupation: baker'),
    ('unlabelled_name', True, 'Alice Example'),
    ('obfuscated_email', True, 'alice [at] example [dot] invalid'),
    ('narrative_combination', True, 'The only centenarian baker in Syntheticville'),
    ('publication', False, 'Publication date: 2024-01-02'),
    ('teaching', False, 'Synthetic teaching evidence'),
    ('aggregate', False, 'Mean age: 65'),
    ('public_contact', False, 'editor@example.invalid'),
]


def evaluate():
    counts = dict(tp=0, tn=0, fp=0, fn=0)
    results = []
    for fixture, risk, text in CASES:
        try:
            PrototypePolicy.screen(text)
            blocked = False
        except WorkflowError:
            blocked = True
        outcome = ('tp' if risk else 'fp') if blocked else ('fn' if risk else 'tn')
        counts[outcome] += 1
        results.append({'fixture': fixture, 'outcome': outcome})
    images = []
    for kind in ('face', 'text', 'blank'):
        image = Image.new('RGB', (256, 256), 'white')
        draw = ImageDraw.Draw(image)
        if kind == 'face':
            draw.ellipse((30, 30, 220, 220), outline='black', width=3)
            draw.ellipse((70, 80, 85, 95), fill='black')
            draw.ellipse((160, 80, 175, 95), fill='black')
            draw.arc((70, 100, 180, 180), 0, 180, fill='black', width=3)
        elif kind == 'text':
            draw.text((10, 60), 'Name: Alice Example', fill='black')
        for fmt in ('PNG', 'JPEG'):
            buffer = BytesIO()
            image.save(buffer, format=fmt)
            with fitz.open() as doc:
                page = doc.new_page()
                page.insert_text((72, 72), 'Publication date: 2024')
                page.insert_image(fitz.Rect(72, 100, 328, 356), stream=buffer.getvalue())
                try:
                    SourceScreening.pdf(doc)
                    status = 'accepted'
                except WorkflowError as error:
                    status = error.code
            images.append({'fixture': f'{kind}_{fmt}', 'gate': status})
    return {
        'text': counts, 'text_cases': results, 'image_cases': images,
        'ocr_executable': bool(shutil.which('tesseract')),
        'packages': {name: importlib.util.find_spec(name) is not None for name in ('tesserocr', 'pytesseract', 'easyocr', 'cv2')},
        'real_ocr_trials': 0, 'face_detection_trials': 0,
        'note': 'Image refusal is not identifier detection. No production OCR configuration qualified.',
    }


if __name__ == '__main__':
    print(json.dumps(evaluate(), indent=2))
