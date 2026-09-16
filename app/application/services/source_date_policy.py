"""Conservative document date evidence; no filesystem dates or user overrides."""

import re
from datetime import date
from xml.etree import ElementTree

from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.source_metadata import SourceDateEvidence


class SourceDatePolicy:
    VERSION = "explicit-scientific-date-v1"
    _line = re.compile(
        r"^(?P<label>publication date|published(?: online)?|date de publication|publié(?:e)?|"
        r"last updated|last update|updated|mis(?:e)? à jour)(?:\s*:\s*|\s+(?:on|in|le|en)\s+)"
        r"(?P<date>\d{4}(?:-\d{2}(?:-\d{2})?)?)\.?$", re.IGNORECASE,
    )
    _namespaces = (
        "http://prismstandard.org/namespaces/basic/2.0/",
        "http://prismstandard.org/namespaces/basic/3.0/",
    )

    @staticmethod
    def missing():
        return WorkflowError("SOURCE_DATE_REQUIRED", "A reliable publication or update date is required. Replace this source with a PDF containing an explicit scientific date.")

    @staticmethod
    def _value(value):
        if not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", value):
            raise SourceDatePolicy.missing()
        parts = [int(part) for part in value.split("-")]
        try:
            earliest = date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)
        except ValueError:
            raise SourceDatePolicy.missing() from None
        if earliest > date.today():
            raise SourceDatePolicy.missing()
        return ("year", "month", "day")[len(parts) - 1]

    @staticmethod
    def xml_root(xml):
        if not xml:
            return None
        if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
            raise SourceDatePolicy.missing()
        try:
            return ElementTree.fromstring(xml)
        except ElementTree.ParseError:
            raise SourceDatePolicy.missing() from None

    @classmethod
    def derive(cls, pages, xml=None):
        candidates = []
        # Restrict text evidence to explicit standalone front-page labels, not
        # arbitrary years in citations, copyright notices or technical metadata.
        first = next((page for page in pages if page.get("page") == 1), None)
        if first:
            for line in str(first.get("text", "")).splitlines()[:40]:
                line = line.strip()
                if line.casefold() in {"references", "bibliography", "références", "bibliographie"}:
                    break
                match = cls._line.fullmatch(line)
                if match:
                    label, value = match.group("label", "date")
                    candidates.append(SourceDateEvidence(
                        value=value, precision=cls._value(value),
                        kind="update" if any(word in label.lower() for word in ("updat", "jour")) else "publication",
                        origin="document_text", page=1, excerpt=line,
                    ))
        root = cls.xml_root(xml)
        if root is not None:
            for namespace in cls._namespaces:
                key = f"{{{namespace}}}publicationDate"
                values = [(element.text or "").strip() for element in root.iter(key)]
                values += [element.attrib[key].strip() for element in root.iter() if key in element.attrib]
                for value in values:
                    candidates.append(SourceDateEvidence(value=value, precision=cls._value(value), kind="publication", origin="scientific_metadata", excerpt=value, metadata_key=key))
        if not candidates:
            raise cls.missing()
        for kind in ("publication", "update"):
            if len({item.value for item in candidates if item.kind == kind}) > 1:
                raise WorkflowError("SOURCE_DATE_CONFLICT", "Conflicting scientific dates were found. Replace the source with an unambiguous version.")
        publications = [item for item in candidates if item.kind == "publication"]
        updates = [item for item in candidates if item.kind == "update"]
        if updates and publications and updates[0].value < publications[0].value:
            raise WorkflowError("SOURCE_DATE_CONFLICT", "The update date precedes publication. Replace the source with an unambiguous version.")
        return (updates or publications)[0]

    @classmethod
    def require(cls, resource):
        if resource._original_content is not None:
            from app.application.services.source_document import SourceDocument
            SourceDocument.verify(resource, resource._original_content)
        # Legacy JSON metadata has no original to substantiate an XMP claim.
        evidence = cls.derive(resource.extracted_pages, resource.metadata.xml_metadata if resource._original_content is not None else None)
        if resource._original_content is None:
            raise WorkflowError("SOURCE_ORIGINAL_REQUIRED", "The original PDF is unavailable, so its date evidence cannot be verified. Reimport this source before scientific use.")
        if resource.metadata.scientific_date is not None and resource.metadata.scientific_date != evidence:
            raise cls.missing()
        return evidence

    @classmethod
    def require_all(cls, resources):
        for resource in resources:
            cls.require(resource)
