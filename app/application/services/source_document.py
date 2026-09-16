"""Read and verify accepted PDF originals in memory, before any durable write."""

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
    def read(filename: str, content: bytes, resource_id: str) -> Resource:
        if not content or len(content) > SourceScreening.MAX_BYTES:
            raise SourceScreening.incomplete()
        try:
            with fitz.open(stream=content, filetype="pdf") as document:
                pages, metadata = SourceScreening.pdf(document)
                xml = document.get_xml_metadata() or None
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
                origin="pdf_memory_import", media_type="application/pdf",
                author=metadata.get("author") or dc_text("creator"),
                publisher=dc_text("publisher"), rights=dc_text("rights"),
                provenance=dc_text("source"),
                locations=[SourceLocation(kind="page", number=page["page"]) for page in pages],
                pdf_metadata={key: str(value) for key, value in metadata.items() if value is not None},
                xml_metadata=xml, scientific_date=scientific_date,
                original_sha256=hashlib.sha256(content).hexdigest(), original_size=len(content),
            ),
        )
        SourceScreening.resource(resource, require_text=True)
        resource._original_content = content
        return resource

    @classmethod
    def verify(cls, resource, content):
        checked = cls.read(resource.filename, content, resource.id)
        # Do not trust hashes, date flags, text, bibliography or locations supplied
        # by a caller; derive them again from the actual original.
        for field in ("file_type", "title", "source", "extracted_text", "extracted_pages", "metadata"):
            if getattr(resource, field) != getattr(checked, field):
                raise WorkflowError("SOURCE_INTEGRITY_FAILED", "Source content or metadata does not match its original PDF. Replace this resource.")
        return content
