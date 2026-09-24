from app.ai.workflows.graph_state import GraphState
from app.application.services.source_document import SourceDocument
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.tests.source_fixtures import dated_resource


def test_new_source_original_is_reparsed_only_once_at_repository_boundary(tmp_path, monkeypatch):
    resource = dated_resource(id="performance-source", filename="performance.pdf")
    repository = UserSessionRepository(tmp_path / "performance.sqlite3")
    calls = 0
    original = SourceDocument.verify.__func__

    def counted(cls, candidate, content):
        nonlocal calls
        calls += 1
        return original(cls, candidate, content)

    monkeypatch.setattr(SourceDocument, "verify", classmethod(counted))
    repository.save(
        "owner", "project", "thread",
        GraphState(prototype_declaration="public", resource_library=[resource]),
    )

    assert calls == 1
