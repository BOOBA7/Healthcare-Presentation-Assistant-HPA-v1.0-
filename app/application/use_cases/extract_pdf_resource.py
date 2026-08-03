from io import BytesIO
from uuid import uuid4

import fitz

from app.domain.enums.resource_type import ResourceType
from app.domain.models.resource import Resource
from app.application.services.patient_case_privacy import PatientCasePrivacyGuard


class ExtractPdfResourceUseCase:
    """Extract readable text and basic metadata from an uploaded PDF."""

    def execute(self, filename: str, content: bytes, *, patient_case_mode: bool = False) -> Resource:
        if not content:
            raise ValueError("The uploaded PDF is empty.")

        try:
            document = fitz.open(stream=BytesIO(content), filetype="pdf")
        except Exception as exc:
            raise ValueError("The uploaded file is not a valid PDF.") from exc

        try:
            pages = [
                {"page": index + 1, "text": page.get_text("text").strip()}
                for index, page in enumerate(document)
            ]
            text = "\n".join(str(page["text"]) for page in pages).strip()
            metadata = document.metadata or {}
        finally:
            document.close()

        if not text:
            raise ValueError("No selectable text was found in this PDF.")

        resource = Resource(
            id=str(uuid4()),
            filename=filename,
            file_type=ResourceType.PDF,
            title=metadata.get("title") or filename,
            source=metadata.get("author") or None,
            extracted_text=text,
            extracted_pages=pages,
            is_validated=True,
        )
        if patient_case_mode:
            PatientCasePrivacyGuard().ensure_resource_safe(resource)
        return resource
