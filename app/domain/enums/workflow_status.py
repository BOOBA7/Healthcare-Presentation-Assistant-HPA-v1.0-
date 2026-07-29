from enum import Enum


class WorkflowStatus(str, Enum):
    """Explicit durable business states for a presentation Project."""

    CONTEXT_COLLECTION = "context_collection"
    AWAITING_RESOURCE_UPLOAD = "awaiting_resource_upload"
    AWAITING_RESOURCE_VALIDATION = "awaiting_resource_validation"
    BLUEPRINT_GENERATION = "blueprint_generation"
    AWAITING_SCOPE_CLARIFICATION = "awaiting_scope_clarification"
    AWAITING_AGENDA_APPROVAL = "awaiting_agenda_approval"
    AWAITING_BLUEPRINT_APPROVAL = "awaiting_blueprint_approval"
    SLIDE_GENERATION = "slide_generation"
    AWAITING_SLIDE_RESOLUTION = "awaiting_slide_resolution"
    AWAITING_SLIDE_APPROVAL = "awaiting_slide_approval"
    AWAITING_FINAL_APPROVAL = "awaiting_final_approval"
    READY_FOR_EXPORT = "ready_for_export"
    EXPORTED = "exported"
