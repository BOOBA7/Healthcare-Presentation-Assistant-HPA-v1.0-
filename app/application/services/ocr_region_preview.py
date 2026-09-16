"""Render an already-screened original region in RAM for its authenticated owner."""
from io import BytesIO
import math

import fitz
from PIL import Image

from app.application.services.source_document import SourceDocument
from app.domain.exceptions.workflow_error import WorkflowError


def region_preview(resource, index):
    if not 0 <= index < len(resource.metadata.ocr_regions):
        raise WorkflowError('OCR_REGION_NOT_FOUND', 'Original region not found.')
    SourceDocument.verify(resource, resource._original_content)
    region = resource.metadata.ocr_regions[index]
    x0, y0, x1, y1 = region.box
    if resource.file_type.value == 'pdf':
        with fitz.open(stream=resource._original_content, filetype='pdf') as doc:
            page = doc[region.page - 1]
            clip = fitz.Rect(x0 * page.rect.width, y0 * page.rect.height,
                             x1 * page.rect.width, y1 * page.rect.height)
            return page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False).tobytes('png')
    with Image.open(BytesIO(resource._original_content)) as image:
        crop = image.crop((math.floor(x0 * image.width), math.floor(y0 * image.height),
                           math.ceil(x1 * image.width), math.ceil(y1 * image.height)))
        output = BytesIO()
        crop.save(output, format='PNG')
        return output.getvalue()
