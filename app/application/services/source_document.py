"""Read and verify accepted source originals in memory, before any durable write."""

import hashlib
from datetime import datetime, timezone

import fitz

from app.application.services.source_date_policy import SourceDatePolicy
from app.application.services.source_screening import SourceScreening
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.resource import Resource
from app.domain.models.source_metadata import SourceLocation, SourceMetadata


class SourceDocument:
    @staticmethod
    def read(filename: str, content: bytes, resource_id: str, *, resource_declaration=None,
             institutional_contacts_confirmed: bool = False) -> Resource:
        if not content or len(content) > SourceScreening.MAX_BYTES:
            raise SourceScreening.incomplete()
        suffix = filename.rsplit('.', 1)[-1].lower()
        if suffix not in ('pdf', 'png', 'jpg', 'jpeg', 'pptx'):
            raise SourceScreening.incomplete()
        if filename.lower().endswith('.pptx') or content.startswith(b'PK'):
            from app.application.services.pptx_document import PptxDocument
            return PptxDocument.read(filename, content, resource_id)
        if content.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8")):
            detected = 'png' if content.startswith(b'\x89PNG') else 'jpeg'
            if suffix not in (('png',) if detected == 'png' else ('jpg', 'jpeg')):
                raise SourceScreening.incomplete()
            from app.application.services.raster_document import RasterDocument
            return RasterDocument.read(filename, content, resource_id)
        if suffix != 'pdf' or not content.startswith(b'%PDF'):
            raise SourceScreening.incomplete()
        try:
            with fitz.open(stream=content, filetype="pdf") as document:
                if any(page.get_images() for page in document):
                    from app.application.services.raster_document import RasterDocument
                    return RasterDocument.read(filename, content, resource_id)
                pages, metadata, privacy = SourceScreening.pdf(
                    document, source_name=filename, resource_declaration=resource_declaration,
                    institutional_contacts_confirmed=institutional_contacts_confirmed,
                )
                xml = document.get_xml_metadata() or None
                from app.application.services.source_assets import pdf_assets
                assets = pdf_assets(content)
        except WorkflowError:
            raise
        except Exception:
            raise SourceScreening.incomplete() from None
        scientific_date = SourceDatePolicy.derive(pages, xml)
        root = SourceDatePolicy.xml_root(xml)

        def dc_text(name):
            if root is None:
                return None
            element = root.find(f".//{{http://purl.org/dc/elements/1.1/}}{name}")
            return " ".join(text.strip() for text in element.itertext() if text.strip()) if element is not None else None

        resource = Resource(
            id=resource_id, filename=filename, file_type="pdf",
            title=metadata.get("title") or dc_text("title") or filename,
            source=metadata.get("author") or dc_text("creator"),
            extracted_pages=pages, extracted_text="\n".join(page["text"] for page in pages).strip(),
            is_validated=True, uploaded_at=datetime.now(timezone.utc),
            metadata=SourceMetadata(
                origin="pdf_memory_import", media_type="application/pdf", assets=assets,
                author=metadata.get("author") or dc_text("creator"),
                publisher=dc_text("publisher"), rights=dc_text("rights"),
                provenance=dc_text("source"),
                locations=[SourceLocation(kind="page", number=page["page"]) for page in pages],
                pdf_metadata={key: str(value) for key, value in metadata.items() if value is not None},
                xml_metadata=xml, scientific_date=scientific_date,
                original_sha256=hashlib.sha256(content).hexdigest(), original_size=len(content),
                extensions=(
                    {"institutional_contacts_confirmed": "true"}
                    if institutional_contacts_confirmed else {}
                ),
                privacy_decision=privacy.decision.value,
                privacy_declaration=privacy.declaration.value if privacy.declaration else None,
                privacy_finding_categories=privacy.report.finding_categories,
                screening_policy_version=privacy.report.screening_policy_version,
                privacy_policy_version=privacy.privacy_policy_version,
            ),
        )
        SourceScreening.resource(resource, require_text=True)
        resource._original_content = content
        return resource

    @classmethod
    def verify(cls, resource, content):
        checked = cls.read(
            resource.filename,
            content,
            resource.id,
            institutional_contacts_confirmed=(
                resource.metadata.extensions.get("institutional_contacts_confirmed") == "true"
            ),
            resource_declaration=resource.metadata.privacy_declaration,
        )
        if resource.metadata.ocr_reviews:
            from app.application.services.ocr_review import apply_reviews, is_reviewed
            if not is_reviewed(resource):
                raise WorkflowError("OCR_REVIEW_UNVERIFIED", "Review must be recorded through the authenticated extraction-review workflow.")
            checked = apply_reviews(checked, resource.metadata.ocr_reviews)
        if resource.metadata.asset_reviews:
            from app.application.services.source_assets import apply_reviews as apply_asset_reviews, is_reviewed as assets_reviewed
            if not assets_reviewed(resource):
                raise WorkflowError("ASSET_REVIEW_UNVERIFIED", "Review must be recorded through the authenticated asset-review workflow.")
            checked = apply_asset_reviews(checked, resource.metadata.asset_reviews)
        # Do not trust hashes, date flags, text, bibliography or locations supplied
        # by a caller; derive them again from the actual original.
        for field in ("file_type", "title", "source", "extracted_text", "extracted_pages", "metadata"):
            if getattr(resource, field) != getattr(checked, field):
                raise WorkflowError("SOURCE_INTEGRITY_FAILED", "Source content or metadata does not match its original. Replace this resource.")
        return content
