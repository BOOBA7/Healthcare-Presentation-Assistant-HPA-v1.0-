"""In-memory, deterministic prototype screening; never a privacy certification."""

import json

from app.application.services.prototype_policy import PrototypePolicy
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.resource import Resource


class SourceScreening:
    VERSION = "source-text-metadata-v1"
    MAX_BYTES = 20 * 1024 * 1024
    MAX_PAGES = 1000

    @staticmethod
    def incomplete():
        return WorkflowError(
            "SOURCE_SCREENING_INCOMPLETE",
            "Source screening could not complete. Use a readable text-only PDF without embedded assets or interactive content.",
        )

    @classmethod
    def resource(cls, resource: Resource, *, require_text: bool = False) -> None:
        """Recheck actual payload on every write, regardless of caller-supplied flags."""
        try:
            payload = resource.model_dump(mode="json")
            checked = Resource.model_validate(payload)
            if checked.file_type.value != "pdf" or checked.metadata.assets or checked.path:
                raise cls.incomplete()
            if len(json.dumps(payload).encode("utf-8")) > cls.MAX_BYTES:
                raise cls.incomplete()
            pages = checked.extracted_pages
            if require_text and not (checked.extracted_text or any(page.get("text", "").strip() for page in pages)):
                raise cls.incomplete()
            if len(pages) > cls.MAX_PAGES:
                raise cls.incomplete()
            numbers = []
            for page in pages:
                if type(page.get("page")) is not int or page["page"] < 1 or not isinstance(page.get("text"), str):
                    raise cls.incomplete()
                numbers.append(page["page"])
            if len(numbers) != len(set(numbers)):
                raise cls.incomplete()
            PrototypePolicy.screen(payload)
        except WorkflowError:
            raise
        except Exception:
            raise cls.incomplete() from None

    @classmethod
    def pdf(cls, document):
        """Screen every extracted surface; unsupported surfaces fail closed, in RAM."""
        try:
            if document.needs_pass or document.embfile_count() or not 0 < len(document) <= cls.MAX_PAGES:
                raise cls.incomplete()
            metadata = document.metadata or {}
            PrototypePolicy.screen(metadata)
            PrototypePolicy.screen(document.get_xml_metadata())
            pages = []
            for index, page in enumerate(document):
                if page.get_images() or page.get_drawings() or list(page.annots() or []) or list(page.widgets() or []) or page.get_links():
                    raise cls.incomplete()
                text = page.get_text("text").strip()
                if not text:
                    raise cls.incomplete()
                PrototypePolicy.screen(text)
                pages.append({"page": index + 1, "text": text})
            return pages, metadata
        except WorkflowError:
            raise
        except Exception:
            raise cls.incomplete() from None
