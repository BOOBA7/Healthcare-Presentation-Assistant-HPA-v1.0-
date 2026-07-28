from app.ai.workflows.graph_state import GraphState
from app.application.use_cases.add_resource import AddResourceUseCase
from app.application.use_cases.create_presentation import CreatePresentationUseCase
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.enums.resource_type import ResourceType
from app.domain.models.resource import Resource
from app.domain.value_objects.presentation_context import PresentationContext
from app.interfaces.api.main import _required_human_action, _resource_response
from app.interfaces.api.job_runner import _job_error_message


def test_resource_api_response_excludes_extracted_pdf_text():
    resource = Resource(
        id="pdf-1",
        filename="evidence.pdf",
        file_type=ResourceType.PDF,
        extracted_text="This must remain server-side.",
        extracted_pages=[{"page": 1, "text": "This must remain server-side."}],
        is_validated=True,
    )

    response = _resource_response(resource)

    assert response["page_count"] == 1
    assert response["characters_extracted"] == len("This must remain server-side.")
    assert "extracted_text" not in response
    assert "extracted_pages" not in response


def test_resource_validation_action_is_available_immediately_after_upload():
    """The web UI must not wait for a model turn to expose the next approval."""
    context = PresentationContext(
        topic="Evidence-based care",
        audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE,
        language=Language.ENGLISH,
        duration_minutes=10,
        objective="Review the uploaded evidence.",
    )
    presentation = CreatePresentationUseCase().execute("Evidence review", context)
    AddResourceUseCase().execute(
        presentation,
        Resource(
            id="pdf-1",
            filename="evidence.pdf",
            file_type=ResourceType.PDF,
            extracted_pages=[{"page": 1, "text": "Evidence for the presentation."}],
            is_validated=True,
        ),
    )

    action = _required_human_action(GraphState(presentation=presentation))

    assert action is not None
    assert action["action"] == "validate_resources"


def test_async_job_exposes_the_api_message_without_http_exception_noise():
    error = HTTPException(
        status_code=409,
        detail={"code": "NO_RELEVANT_PASSAGE", "message": "No relevant PDF passage was found."},
    )

    assert _job_error_message(error) == "No relevant PDF passage was found."
from fastapi import HTTPException
