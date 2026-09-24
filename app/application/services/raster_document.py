"""Bounded raster extraction in RAM; originals are accepted only after all gates.

Only PNG/JPEG and simple full-page image-only PDFs are supported. No staging
files, opaque metadata, overlays, mixed pages or unconfirmed scientific use.
"""
import hashlib
from io import BytesIO
import time
import warnings

import fitz
from PIL import Image

from app.application.services.local_image_screening import LocalImageScreening
from app.application.services.prototype_policy import PrototypePolicy
from app.application.services.raster_privacy import screen_raster_text
from app.application.services.source_date_policy import SourceDatePolicy
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.resource import Resource
from app.domain.models.source_metadata import SourceLocation, SourceMetadata


class RasterDocument:
    MAX_SECONDS = 60
    MIN_DATE_CONFIDENCE = 0.98

    @staticmethod
    def image(content):
        """Decode once, reject uninspectable metadata, render into a memory buffer."""
        metadata = {}
        xml = None
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format not in ('PNG', 'JPEG') or getattr(image, 'n_frames', 1) != 1:
                    raise LocalImageScreening.incomplete()
                if image.width * image.height > LocalImageScreening.MAX_PIXELS:
                    raise LocalImageScreening.incomplete()
                # Alpha/EXIF orientation can hide or move content; do not silently
                # flatten, rotate or strip these unqualified surfaces.
                if image.mode not in ('RGB', 'L') or image.getexif():
                    raise LocalImageScreening.incomplete()
                kind = image.format.lower()
                for key, value in image.info.items():
                    if key == 'xmp' and isinstance(value, bytes):
                        key, value = 'XML:com.adobe.xmp', value.decode('utf-8', errors='strict')
                    if key in ('jfif', 'jfif_version', 'jfif_unit', 'jfif_density', 'dpi'):
                        if not isinstance(value, (int, float, tuple)):
                            raise LocalImageScreening.incomplete()
                        continue
                    if key not in ('Title', 'Author', 'Description', 'Copyright', 'Software', 'XML:com.adobe.xmp'):
                        raise LocalImageScreening.incomplete()
                    if not isinstance(value, str) or len(value) > 100_000:
                        raise LocalImageScreening.incomplete()
                    PrototypePolicy.screen(key)
                    screen_raster_text(value)
                    metadata[key] = value
                    if key == 'XML:com.adobe.xmp':
                        xml = value
                        cls_root = SourceDatePolicy.xml_root(xml)
                        allowed_namespaces = ('adobe:ns:meta/', 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                                              'http://prismstandard.org/namespaces/basic/2.0/', 'http://prismstandard.org/namespaces/basic/3.0/',
                                              'http://purl.org/dc/elements/1.1/')
                        if cls_root is not None:
                            for element in cls_root.iter():
                                for tag in (element.tag, *element.attrib):
                                    if not any(tag.startswith('{' + namespace + '}') for namespace in allowed_namespaces):
                                        raise LocalImageScreening.incomplete()
                image.load()
                output = BytesIO()
                image.convert('RGB').save(output, format='PNG')
        return kind, output.getvalue(), metadata, xml

    @classmethod
    def read(cls, filename, content, resource_id):
        start = time.monotonic()
        screen_raster_text(filename)
        regions, pages, image_metadata = [], [], {}
        pdf_metadata = {}
        xml = None
        try:
            def inspect(png, number):
                if time.monotonic() - start > cls.MAX_SECONDS:
                    raise LocalImageScreening.incomplete()
                result = LocalImageScreening.inspect(png)
                if time.monotonic() - start > cls.MAX_SECONDS:
                    raise LocalImageScreening.incomplete()
                if not result.lines:
                    raise LocalImageScreening.incomplete()
                text = '\n'.join(line.text for line in result.lines)
                screen_raster_text(text)
                for line in result.lines:
                    # Never accept caller/engine-supplied confirmation state.
                    regions.append(line.model_copy(update={'page': number}))
                pages.append({'page': number, 'text': text})

            if content.startswith(b'%PDF'):
                kind = 'pdf'
                with fitz.open(stream=content, filetype='pdf') as doc:
                    if doc.needs_pass or doc.embfile_count() or not 0 < len(doc) <= LocalImageScreening.MAX_PAGES:
                        raise LocalImageScreening.incomplete()
                    pdf_metadata = {k: str(v) for k, v in (doc.metadata or {}).items() if v is not None}
                    xml = doc.get_xml_metadata() or None
                    for value in pdf_metadata.values():
                        screen_raster_text(value)
                    if xml:
                        screen_raster_text(xml)
                    for number, page in enumerate(doc, 1):
                        images = page.get_images(full=True)
                        if (len(images) != 1 or images[0][1] or page.get_text().strip() or page.get_drawings()
                                or list(page.annots() or []) or list(page.widgets() or []) or page.get_links()
                                or page.rotation or page.cropbox != page.mediabox):
                            raise LocalImageScreening.incomplete()
                        rects = page.get_image_rects(images[0][0])
                        if len(rects) != 1 or rects[0] != page.rect:
                            raise LocalImageScreening.incomplete()
                        if page.rect.width * page.rect.height * 4 > LocalImageScreening.MAX_PIXELS:
                            raise LocalImageScreening.incomplete()
                        embedded = doc.extract_image(images[0][0])
                        _, _, embedded_metadata, embedded_xml = cls.image(embedded['image'])
                        # Embedded scientific metadata is not whole-document date proof.
                        if embedded_xml:
                            SourceDatePolicy.xml_root(embedded_xml)
                        image_metadata.update({f'{number}:{k}': v for k, v in embedded_metadata.items()})
                        png = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).tobytes('png')
                        inspect(png, number)
            else:
                kind, png, image_metadata, xml = cls.image(content)
                inspect(png, 1)
            # Prefer a recognized document-level scientific metadata date. An
            # OCR date is admissible only with high confidence for its exact line.
            evidence = SourceDatePolicy.derive(pages, xml)
            if evidence.origin == 'document_text':
                matches = [line for line in regions if line.page == evidence.page and line.text.strip() == evidence.excerpt]
                if not matches or any(line.confidence < cls.MIN_DATE_CONFIDENCE for line in matches):
                    if xml:
                        evidence = SourceDatePolicy.derive([], xml)
                    else:
                        raise WorkflowError('SOURCE_DATE_UNCERTAIN', 'The OCR publication date is uncertain. Supply reliable scientific date metadata or replace the source.')
                else:
                    evidence = evidence.model_copy(update={'origin': 'ocr_text'})
            resource = Resource(
                id=resource_id, filename=filename, file_type=kind,
                title=pdf_metadata.get('title') or image_metadata.get('Title') or filename,
                source=pdf_metadata.get('author') or image_metadata.get('Author'),
                extracted_pages=pages, extracted_text='\n'.join(page['text'] for page in pages),
                is_validated=False,
                metadata=SourceMetadata(
                    origin='raster_memory_import', media_type='application/pdf' if kind == 'pdf' else f'image/{kind}',
                    original_sha256=hashlib.sha256(content).hexdigest(), original_size=len(content),
                    pdf_metadata=pdf_metadata, xml_metadata=xml, image_metadata=image_metadata,
                    scientific_date=evidence, ocr_engine=LocalImageScreening.ENGINE, ocr_regions=regions,
                    locations=[SourceLocation(kind='region', number=line.page, region=line.box) for line in regions],
                ),
            )
            if kind == "pdf":
                from app.application.services.source_assets import optional_pdf_assets
                resource.metadata.assets = optional_pdf_assets(content, raster=True)
            from app.application.services.source_screening import SourceScreening
            SourceScreening.resource(resource, require_text=True)
            resource._original_content = content
            return resource
        except WorkflowError:
            raise
        except (Exception, KeyboardInterrupt):
            raise LocalImageScreening.incomplete() from None
