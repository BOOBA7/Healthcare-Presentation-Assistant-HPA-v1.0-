from app.domain.enums.resource_type import ResourceType
from app.domain.models.resource import Resource
from app.interfaces.api.main import _resource_response


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
