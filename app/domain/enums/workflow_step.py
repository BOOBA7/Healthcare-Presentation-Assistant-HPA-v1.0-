from enum import Enum


class WorkflowStep(str, Enum):
    """
    Represents the current step of the presentation generation workflow.
    """

    RESOURCE_VALIDATION = "Resource Validation"
    AUDIENCE_VALIDATION = "Audience Validation"
    CONTEXT_VALIDATION = "Context Validation"

    BLUEPRINT_GENERATION = "Blueprint Generation"
    BLUEPRINT_VALIDATION = "Blueprint Validation"

    SLIDE_GENERATION = "Slide Generation"
    SLIDE_VALIDATION = "Slide Validation"

    PRESENTATION_REVIEW = "Presentation Review"

    EXPORT = "Export"

    COMPLETED = "Completed"
