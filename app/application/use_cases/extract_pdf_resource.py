from io import BytesIO
from uuid import uuid4

import fitz

from app.domain.enums.resource_type import ResourceType
from app.domain.models.resource import Resource


class ExtractPdfResourceUseCase:
    """Extract readable text and basic metadata from an uploaded PDF."""

    def execute(self, filename: str, content: bytes) -> Resource:
        if not content:
            raise ValueError("The uploaded PDF is empty.")

        try:
            document = fitz.open(stream=BytesIO(content), filetype="pdf")
        except Exception as exc:
            raise ValueError("The uploaded file is not a valid PDF.") from exc

        try:
            text = "\n".join(page.get_text("text") for page in document).strip()
            metadata = document.metadata or {}
        finally:
            document.close()

        if not text:
            raise ValueError("No selectable text was found in this PDF.")

        return Resource(
            id=str(uuid4()),
            filename=filename,
            file_type=ResourceType.PDF,
            title=metadata.get("title") or filename,
            source=metadata.get("author") or None,
            extracted_text=text,
            is_validated=True,
        )
