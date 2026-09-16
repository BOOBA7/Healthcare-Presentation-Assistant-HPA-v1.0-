from uuid import uuid4

from app.application.services.prototype_policy import PrototypePolicy
from app.application.services.source_document import SourceDocument
from app.domain.models.resource import Resource


class ExtractPdfResourceUseCase:
    """Screen and extract a dated PDF in memory before accepting its original."""

    def execute(self, filename: str, content: bytes, *, patient_case_mode: bool = False, prototype_declaration: str | None = None) -> Resource:
        PrototypePolicy.declaration(prototype_declaration, patient_case_mode=patient_case_mode)
        PrototypePolicy.screen(filename)
        return SourceDocument.read(filename, content, str(uuid4()))
