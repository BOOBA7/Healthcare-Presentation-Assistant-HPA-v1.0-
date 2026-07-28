from app.ai.workflows.graph_state import GraphState
from app.domain.models.user_profile import UserProfile
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.application.services.conversation_history import add_turn, ensure_history
from langchain_core.messages import AIMessage, HumanMessage


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
    assert {project["id"] for project in repository.list_projects("user-1")} == {"project-a", "project-b"}


def test_message_types_are_preserved_after_sqlite_reload(tmp_path):
    repository = UserSessionRepository(tmp_path / "sessions.sqlite3")
    state = GraphState(messages=[HumanMessage(content="Hello"), AIMessage(content="Hi")])

    repository.save("user-1", "project-a", "thread-1", state, "My project")
    _, restored = repository.load("user-1", "project-a")

    assert isinstance(restored.messages[0], HumanMessage)
    assert isinstance(restored.messages[1], AIMessage)
    assert repository.list_projects("user-1") == [{"id": "project-a", "name": "My project"}]


def test_ui_conversation_history_is_restored_independently_from_model_messages(tmp_path):
    repository = UserSessionRepository(tmp_path / "sessions.sqlite3")
    state = GraphState(messages=[HumanMessage(content="Hello"), AIMessage(content="Hi")])
    assert ensure_history(state)
    add_turn(state, "user", "Can we discuss the uploaded guideline first?")

    repository.save("user-1", "project-a", "thread-1", state)
    _, restored = repository.load("user-1", "project-a")

    assert [(turn.role, turn.text) for turn in restored.conversation_history] == [
        ("user", "Hello"),
        ("assistant", "Hi"),
        ("user", "Can we discuss the uploaded guideline first?"),
    ]


def test_passwords_are_hashed_and_tokens_authenticate_users(tmp_path):
    repository = UserSessionRepository(tmp_path / "sessions.sqlite3")
    profile = UserProfile(
        professional_role="professor_medicine",
        preferred_language="ar",
    )
    repository.register_user("anis", "a-safe-password", profile)

    assert repository.authenticate_user("anis", "a-safe-password")
    assert not repository.authenticate_user("anis", "wrong-password")
    assert repository.user_for_token(repository.create_auth_token("anis")) == "anis"
    assert repository.get_user_profile("anis") == profile

    updated_profile = UserProfile(
        professional_role="veterinarian",
        preferred_language="fr",
    )
    repository.update_user_profile("anis", updated_profile)

    assert repository.get_user_profile("anis") == updated_profile


def test_pharmacist_is_a_supported_professional_profile():
    profile = UserProfile(professional_role="pharmacist", preferred_language="fr")

    assert profile.professional_role == "pharmacist"


def test_local_password_reset_and_user_templates(tmp_path):
    repository = UserSessionRepository(tmp_path / "sessions.sqlite3")
    repository.register_user("anis", "old-safe-password")

    repository.reset_password_without_verification("anis", "new-safe-password")
    template = repository.save_presentation_template("anis", "my-theme.pptx", b"template-content")

    assert not repository.authenticate_user("anis", "old-safe-password")
    assert repository.authenticate_user("anis", "new-safe-password")
    assert repository.list_presentation_templates("anis") == [template]
    assert repository.presentation_template_path("anis", template["id"]).read_bytes() == b"template-content"

    repository.delete_user("anis")

    assert repository.presentation_template_path("anis", template["id"]) is None


def test_project_audit_events_are_scoped_and_removed_with_the_project(tmp_path):
    repository = UserSessionRepository(tmp_path / "sessions.sqlite3")
    repository.create_empty("user-1", "project-a", "Clinical review")
    repository.record_event(
        "user-1",
        "project-a",
        "RESOURCE_UPLOADED",
        "user",
        {"resource_id": "pdf-1", "workflow_version": "business-graph-v1"},
    )

    events = repository.list_events("user-1", "project-a")

    assert [event["event_type"] for event in events] == ["RESOURCE_UPLOADED", "PROJECT_CREATED"]
    assert events[0]["payload"]["resource_id"] == "pdf-1"

    assert repository.delete_project("user-1", "project-a")
    assert repository.list_events("user-1", "project-a") == []


def test_state_and_audit_event_are_written_together(tmp_path):
    repository = UserSessionRepository(tmp_path / "sessions.sqlite3")
    state = GraphState()
    state.conversation_context.topic = "One transaction"

    repository.save_with_event(
        "user-1", "project-a", "thread-1", state,
        "PROJECT_STATE_SAVED", "system", {"reason": "test"}, "Atomic project",
    )

    _, restored = repository.load("user-1", "project-a")
    events = repository.list_events("user-1", "project-a")
    assert restored.conversation_context.topic == "One transaction"
    assert [(event["event_type"], event["payload"]["reason"]) for event in events] == [
        ("PROJECT_STATE_SAVED", "test")
    ]


def test_job_progress_is_durable_and_scoped_to_the_user(tmp_path):
    repository = UserSessionRepository(tmp_path / "sessions.sqlite3")
    repository.create_empty("user-1", "project-a")
    job = repository.create_job("user-1", "project-a", "resources")

    repository.update_job(
        "user-1", job["job_id"], status="running", progress=65, stage="generating_overview"
    )

    restored = repository.get_job("user-1", job["job_id"])
    assert restored is not None
    assert restored["status"] == "running"
    assert restored["progress"] == 65
    assert restored["stage"] == "generating_overview"
    assert repository.get_job("another-user", job["job_id"]) is None
