"""04.2 stores screened OCR for later review; it is never model evidence yet."""
from app.domain.exceptions.workflow_error import WorkflowError
from app.application.services.ocr_review import is_reviewed


def require_confirmed_ocr(resources):
    if any((resource.metadata.ocr_engine or resource.metadata.ocr_regions
           or resource.metadata.origin == 'raster_memory_import'
           or resource.file_type.value in ('png', 'jpeg')) and not is_reviewed(resource) for resource in resources):
        raise WorkflowError('OCR_CONFIRMATION_REQUIRED',
                            'OCR extraction is unconfirmed; model processing and generation are blocked until every region is reviewed.')
