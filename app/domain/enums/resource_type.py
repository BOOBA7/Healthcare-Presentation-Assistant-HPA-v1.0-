from enum import Enum


class ResourceType(str, Enum):
    """
    Supported scientific resource types.
    """

    PDF = "pdf"

    PNG = "png"

    JPEG = "jpeg"

    DOCX = "docx"

    PPTX = "pptx"

    TXT = "txt"

    HTML = "html"

    MARKDOWN = "md"
