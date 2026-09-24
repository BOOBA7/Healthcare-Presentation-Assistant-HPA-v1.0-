from uuid import uuid4

from app.application.services.prototype_policy import PrototypePolicy
from app.application.services.source_document import SourceDocument
from app.domain.models.resource import Resource


class ExtractPdfResourceUseCase:
    """Screen dated PDF/PNG/JPEG/PPTX in memory; retain the legacy use-case name."""

    def execute(self, filename: str, content: bytes, *, patient_case_mode: bool = False,
                prototype_declaration: str | None = None,
                resource_declaration: str | None = None,
                institutional_contacts_confirmed: bool = False) -> Resource:
        PrototypePolicy.declaration(prototype_declaration, patient_case_mode=patient_case_mode)
        PrototypePolicy.screen(filename)
        return SourceDocument.read(
            filename, content, str(uuid4()),
            resource_declaration=resource_declaration,
            institutional_contacts_confirmed=institutional_contacts_confirmed,
        )
