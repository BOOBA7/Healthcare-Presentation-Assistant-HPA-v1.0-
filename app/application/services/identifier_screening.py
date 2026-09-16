"""Bounded EN/FR identifier heuristics; no anonymisation assurance or NER."""
import re
import unicodedata

from app.domain.exceptions.workflow_error import WorkflowError


class IdentifierScreening:
    MAX_CHARS = 2_000_000
    PATTERNS = {
        'name': r'\b(?:name|nom|pr[eé]nom)\s*:\s*[a-zà-ÿ]+',
        'contact': r'\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b|\b(?:phone|telephone|téléphone|tel|fax)\s*:\s*\+?\d|(?<!\w)\+\d[\d ()-]{7,}\d',
        'identifier': r'\b(?:record number|administrative id|passport|passeport|ssn|mrn|numéro de dossier)\s*[:#-]\s*\w+',
        'identifying date': r'\b(?:date of birth|birth date|dob|date de naissance|né[e]? le|admission|discharge)\s*[: ]\s*\d',
        'address': r'\b\d{1,5}\s+(?:rue|avenue|boulevard|route)\s+\w+|\b\d{1,5}\s+\w+\s+(?:street|road|avenue)\b',
    }
    COMPILED = {key: re.compile(value, re.I) for key, value in PATTERNS.items()}

    @classmethod
    def findings(cls, text):
        text = unicodedata.normalize('NFKC', text)
        found = [key for key, pattern in cls.COMPILED.items() if pattern.search(text)]
        if re.search(r'\b(?:age|âge)\s*:', text, re.I) and re.search(r'\b(?:village|postcode|code postal|occupation|profession)\s*:', text, re.I):
            found.append('risky combination')
        return found

    @classmethod
    def screen(cls, text):
        if len(text) > cls.MAX_CHARS:
            raise WorkflowError('SOURCE_SCREENING_INCOMPLETE', 'Identifier screening exceeded its text limit.')
        try:
            found = cls.findings(text)
        except Exception:
            raise WorkflowError('SOURCE_SCREENING_INCOMPLETE', 'Identifier screening could not complete.') from None
        if found:
            raise WorkflowError('POSSIBLE_IDENTIFIER_DETECTED', 'Possible identifying information detected. Remove identifiers before continuing; automated checks cannot guarantee anonymisation.')
