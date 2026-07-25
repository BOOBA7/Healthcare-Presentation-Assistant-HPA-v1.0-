from app.ai.workflows.graph_state import GraphState
from app.interfaces.storage.user_session_repository import UserSessionRepository


def test_user_session_is_restored_from_sqlite(tmp_path):
    repository = UserSessionRepository(tmp_path / "sessions.sqlite3")
    state = GraphState()
    state.conversation_context.topic = "Depression"

    repository.save("user-1", "project-a", "thread-1", state)
    thread_id, restored = repository.load("user-1", "project-a")

    assert thread_id == "thread-1"
    assert restored.conversation_context.topic == "Depression"


def test_user_can_keep_independent_projects(tmp_path):
    repository = UserSessionRepository(tmp_path / "sessions.sqlite3")
    first_thread, first_state = repository.create_empty("user-1", "project-a")
    second_thread, second_state = repository.create_empty("user-1", "project-b")

    first_state.conversation_context.topic = "Depression"
    second_state.conversation_context.topic = "Diabetes"
    repository.save("user-1", "project-a", first_thread, first_state)
    repository.save("user-1", "project-b", second_thread, second_state)

    _, restored_first = repository.load("user-1", "project-a")
    _, restored_second = repository.load("user-1", "project-b")

    assert restored_first.conversation_context.topic == "Depression"
    assert restored_second.conversation_context.topic == "Diabetes"
    assert set(repository.list_project_ids("user-1")) == {"project-a", "project-b"}
