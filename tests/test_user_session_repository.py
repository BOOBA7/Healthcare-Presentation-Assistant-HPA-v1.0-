from app.ai.workflows.graph_state import GraphState
from app.interfaces.storage.user_session_repository import UserSessionRepository


def test_user_session_is_restored_from_sqlite(tmp_path):
    repository = UserSessionRepository(tmp_path / "sessions.sqlite3")
    state = GraphState()
    state.conversation_context.topic = "Depression"

    repository.save("user-1", "thread-1", state)
    thread_id, restored = repository.load("user-1")

    assert thread_id == "thread-1"
    assert restored.conversation_context.topic == "Depression"
