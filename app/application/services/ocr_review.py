"""Immutable extraction + append-only human reviews; no client-supplied approval."""
import hashlib
import json

from app.application.services.raster_privacy import screen_raster_text
from app.application.services.source_date_policy import SourceDatePolicy
from app.domain.exceptions.workflow_error import WorkflowError


def review_digest(resource):
    return hashlib.sha256(json.dumps({
        'id': resource.id, 'original': resource.metadata.original_sha256,
        'reviews': [review.model_dump(mode='json') for review in resource.metadata.ocr_reviews],
    }, sort_keys=True).encode()).hexdigest()


def is_reviewed(resource):
    return bool(resource.metadata.ocr_reviews and resource._ocr_review_receipt == review_digest(resource))


def apply_reviews(original, reviews):
    """Called only after repository authority has been checked, not from JSON."""
    result = original.model_copy(deep=True)
    count = len(original.metadata.ocr_regions)
    if not count or not reviews:
        raise WorkflowError('OCR_CONFIRMATION_REQUIRED', 'Confirm every OCR region against its original before continuing.')
    batches = sorted({review.batch for review in reviews})
    if batches != list(range(1, len(batches) + 1)):
        raise WorkflowError('OCR_REVIEW_INVALID', 'Review history is incomplete.')
    for batch in batches:
        rows = [review for review in reviews if review.batch == batch]
        if sorted(review.region_index for review in rows) != list(range(count)):
            raise WorkflowError('OCR_REVIEW_INVALID', 'Every region requires explicit confirmation.')
        for review in rows:
            if (review.original_sha256 != original.metadata.original_sha256
                    or review.original_value != original.metadata.ocr_regions[review.region_index].text):
                raise WorkflowError('OCR_REVIEW_INVALID', 'Review does not match its original source.')
            screen_raster_text(review.corrected_value)
    latest = {review.region_index: review for review in reviews if review.batch == batches[-1]}
    pages = {}
    for index, region in enumerate(original.metadata.ocr_regions):
        pages.setdefault(region.page, []).append(latest[index].corrected_value)
    result.extracted_pages = [{'page': page, 'text': '\n'.join(lines)} for page, lines in sorted(pages.items())]
    result.extracted_text = '\n'.join(page['text'] for page in result.extracted_pages)
    evidence = SourceDatePolicy.derive(result.extracted_pages, result.metadata.xml_metadata)
    if evidence.origin == 'document_text':
        evidence = evidence.model_copy(update={'origin': 'user_confirmed'})
    result.metadata.scientific_date = evidence
    result.metadata.ocr_reviews = reviews
    result.is_validated = True
    result._ocr_review_receipt = review_digest(result)
    return result
