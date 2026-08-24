from langchain_core.messages import AIMessage

from app.application.use_cases.summarize_resources import SummarizeResourcesUseCase
from app.domain.enums.resource_type import ResourceType
from app.domain.models.resource import Resource


class _FakeModel:
    def invoke(self, _messages):
        return AIMessage(
            content="Overall idea: the guideline supports structured follow-up "
            "[[cite: pdf-1 | p. 1 | Structured follow-up is recommended.]].\n"
            "Limitation: no population detail is provided "
            "[[cite: pdf-1 | p. 1 | Structured follow-up is recommended.]]."
        )


def test_resource_analysis_uses_uploaded_pdf_context(monkeypatch):
    resources = [
        Resource(
            id="pdf-1",
            filename="guideline.pdf",
            file_type=ResourceType.PDF,
            extracted_pages=[{"page": 1, "text": "Structured follow-up is recommended."}],
            is_validated=True,
        )
    ]
    monkeypatch.setattr("app.application.use_cases.summarize_resources.get_llm", lambda: _FakeModel())

    analysis = SummarizeResourcesUseCase().execute(resources, language="en")

    assert analysis.resource_ids == ["pdf-1"]
    assert "structured follow-up" in analysis.summary


def test_resource_analysis_rejects_an_unverifiable_citation(monkeypatch):
    class InvalidCitationModel:
        def invoke(self, _messages):
            return AIMessage(content="Unsupported claim [[cite: pdf-1 | p. 2 | Not present in the PDF.]].")

    resources = [
        Resource(
            id="pdf-1",
            filename="guideline.pdf",
            file_type=ResourceType.PDF,
            extracted_pages=[{"page": 1, "text": "Structured follow-up is recommended."}],
            is_validated=True,
        )
    ]
    monkeypatch.setattr("app.application.use_cases.summarize_resources.get_llm", lambda: InvalidCitationModel())

    import pytest

    with pytest.raises(ValueError, match="PDF page|evidence excerpt"):
        SummarizeResourcesUseCase().execute(resources, language="en")
