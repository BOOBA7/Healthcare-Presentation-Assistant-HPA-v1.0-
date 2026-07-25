from enum import Enum


class SlideStatus(str, Enum):
    DRAFT = "Draft"
    GENERATED = "Generated"
    VALIDATED = "Validated"
