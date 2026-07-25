from enum import Enum


class PresentationStatus(str, Enum):
    """
    Represents the lifecycle status of a presentation.
    """

    DRAFT = "Draft"

    IN_PROGRESS = "In Progress"

    WAITING_VALIDATION = "Waiting Validation"

    COMPLETED = "Completed"

    ARCHIVED = "Archived"
