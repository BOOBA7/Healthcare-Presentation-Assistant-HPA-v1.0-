from langchain_core.messages import AIMessage
import pytest

from app.application.use_cases.discuss_resources import DiscussResourcesUseCase
from app.domain.enums.resource_type import ResourceType
from app.domain.models.resource import Resource


def _resource() -> Resource:
    return Resource(
        id="pdf-1",
        filename="guideline.pdf",
        file_type=ResourceType.PDF,
        extracted_pages=[{"page": 1, "text": "Structured follow-up is recommended after treatment initiation."}],
        is_validated=True,
    )


def test_resource_discussion_accepts_a_verified_citation(monkeypatch):
    class VerifiedModel:
        def invoke(self, _messages):
            return AIMessage(
                content=(
                    "The supplied PDF supports structured follow-up "
                    "[[cite: pdf-1 | p. 1 | Structured follow-up is recommended after treatment initiation.]]."
                )
            )

    monkeypatch.setattr("app.application.use_cases.discuss_resources.get_llm", lambda: VerifiedModel())

    answer = DiscussResourcesUseCase().execute(
        [_resource()], "What structured follow-up is recommended after treatment initiation?"
    )

    assert "[[cite: pdf-1 | p. 1" in answer


def test_resource_discussion_rejects_an_unknown_resource_citation(monkeypatch):
    class InvalidModel:
        def invoke(self, _messages):
            return AIMessage(content="Unsupported claim [[cite: unknown | p. 1 | Some evidence excerpt.]].")

    monkeypatch.setattr("app.application.use_cases.discuss_resources.get_llm", lambda: InvalidModel())

    with pytest.raises(ValueError, match="unknown uploaded PDF resource"):
        DiscussResourcesUseCase().execute(
            [_resource()], "What structured follow-up is recommended after treatment initiation?"
        )
