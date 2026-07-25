from enum import Enum


class Intent(str, Enum):
    """
    Represents all user intentions supported
    by the Healthcare Presentation Assistant.
    """

    # Conversation
    GREETING = "greeting"

    HELP = "help"

    UNKNOWN = "unknown"

    # Presentation lifecycle
    CREATE_PRESENTATION = "create_presentation"

    UPDATE_PRESENTATION = "update_presentation"

    DELETE_PRESENTATION = "delete_presentation"

    # Resources
    ADD_RESOURCE = "add_resource"

    REMOVE_RESOURCE = "remove_resource"

    LIST_RESOURCES = "list_resources"

    # Blueprint
    GENERATE_BLUEPRINT = "generate_blueprint"

    REVIEW_BLUEPRINT = "review_blueprint"

    REGENERATE_BLUEPRINT = "regenerate_blueprint"

    # Slides
    GENERATE_SLIDES = "generate_slides"

    GENERATE_SLIDE = "generate_slide"

    REGENERATE_SLIDE = "regenerate_slide"

    UPDATE_SLIDE = "update_slide"

    DELETE_SLIDE = "delete_slide"

    REVIEW_SLIDES = "review_slides"

    # Presentation
    SHOW_PRESENTATION = "show_presentation"

    SUMMARY = "summary"

    # Export
    EXPORT_POWERPOINT = "export_powerpoint"

    EXPORT_PDF = "export_pdf"

    EXPORT_WORD = "export_word"

    # Workflow
    STATUS = "status"

    RESET_SESSION = "reset_session"

    CANCEL = "cancel"

    # Scientific QA
    ASK_QUESTION = "ask_question"

    EXPLAIN = "explain"

    SEARCH_RESOURCE = "search_resource"
