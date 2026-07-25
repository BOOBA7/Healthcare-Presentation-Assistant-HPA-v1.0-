from enum import Enum


class ResourceType(str, Enum):
    """
    Supported scientific resource types.
    """

    PDF = "pdf"

    DOCX = "docx"

    PPTX = "pptx"

    TXT = "txt"

    HTML = "html"

    MARKDOWN = "md"
