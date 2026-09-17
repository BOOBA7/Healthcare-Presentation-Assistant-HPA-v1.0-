"""In-memory, deterministic prototype screening; never a privacy certification."""

import json

from app.application.services.prototype_policy import PrototypePolicy
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.resource import Resource


class SourceScreening:
    VERSION = "source-pptx-metadata-v4"
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
            raster = checked.metadata.origin == "raster_memory_import"
            pptx = checked.metadata.origin == "pptx_memory_import"
            if (checked.metadata.assets and checked.file_type.value not in ("pptx", "pdf")) or checked.path:
                raise cls.incomplete()
            if raster:
                from app.application.services.local_image_screening import LocalImageScreening
                if (checked.file_type.value not in ("pdf", "png", "jpeg")
                        or checked.metadata.ocr_engine != LocalImageScreening.ENGINE
                        or not checked.metadata.ocr_regions
                        or checked.is_validated != bool(checked.metadata.ocr_reviews)):
                    raise cls.incomplete()
            elif pptx:
                from app.application.services.raster_privacy import screen_raster_text

                def screen_strings(value):
                    if isinstance(value, str):
                        screen_raster_text(value)
                    elif isinstance(value, dict):
                        for item in value.values():
                            screen_strings(item)
                    elif isinstance(value, list):
                        for item in value:
                            screen_strings(item)

                screen_strings(payload)
                if (checked.file_type.value != "pptx" or checked.metadata.ocr_engine
                        or checked.metadata.ocr_regions or checked.metadata.ocr_reviews
                        or any(asset.location.kind != "slide" for asset in checked.metadata.assets)):
                    raise cls.incomplete()
            elif checked.file_type.value != "pdf" or checked.metadata.ocr_engine or checked.metadata.ocr_regions or checked.metadata.ocr_reviews:
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
