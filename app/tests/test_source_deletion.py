"""03.3: synthetic-only lifecycle, recovery and direct repository boundaries."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from app.ai.workflows.graph_state import GraphState
from app.application.use_cases.manage_project_resources import RemoveProjectResourceUseCase
from app.domain.exceptions.concurrent_modification_error import ConcurrentModificationError
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.conversation_turn import ConversationTurn
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.tests import test_source_lifecycle as lifecycle
from app.tests.test_source_preservation import read, pdf

workspace = lifecycle.workspace


def populated(repository, user="owner", project="one", source=None):
    source = source or read()
    state = GraphState(prototype_declaration="synthetic", resource_library=[source],
                       presentation=lifecycle.presentation([source]))
    state.messages = [AIMessage(content="Synthetic derived quote")]
    state.resource_conversation_history = [ConversationTurn(role="assistant", text="Synthetic derived quote")]
    state.conversation_memory_summary = "Synthetic derived quote"
    state.presentation.state.presentation_validated = True
    repository.save_with_event(user, project, "thread", state, "GENERATED", user, {"quote": "Synthetic derived quote"})
    return state


def test_removal_retains_library_and_reattachment_survives_restart(workspace):
    client, repository = workspace
    content = pdf()
    identifier = lifecycle.upload(client, content).json()["resource_id"]
    base = "/projects/synthetic-owner/demo"
    response = client.delete(base + f"/resources/{identifier}")
    assert response.status_code == 200
    assert response.json()["resource_library"] == []
    assert response.json()["owner_library"][0]["id"] == identifier
    reopened = UserSessionRepository(repository.database_path)
    assert reopened.library_resource("synthetic-owner", identifier)._original_content == content
    assert client.post(base + f"/library/{identifier}").status_code == 200
    assert reopened.load("synthetic-owner", "demo")[1].resource_library[0]._original_content == content


def test_permanent_deletion_clears_every_project_copy_and_fences_jobs(tmp_path):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    source = read()
    stale = populated(repository, source=source).model_copy(deep=True)
    populated(repository, project="two", source=source)
    populated(repository, user="other", source=source)
    job = repository.create_job("owner", "one", "blueprint")
    repository.update_job("owner", job["job_id"], status="completed", progress=100, stage="done", result={"quote": "Synthetic derived quote"})
    result = repository.permanently_delete_source("owner", source.id, "owner")
    assert result == {"resource_id": source.id, "deleted": True, "cleanup_pending": False}
    assert repository.list_library_resources("owner") == []
    assert repository.library_resource("other", source.id)._original_content == source._original_content
    for project in ("one", "two"):
        state = repository.load("owner", project)[1]
        assert state.resource_library == [] and state.presentation.resources == []
        assert not state.messages and not state.resource_conversation_history and not state.conversation_memory_summary
        assert not state.presentation.state.presentation_validated
        assert not repository.load_resource_chunks("owner", project)
        assert "Synthetic derived quote" not in json.dumps(repository.list_events("owner", project))
    cancelled = repository.get_job("owner", job["job_id"])
    assert cancelled["status"] == "cancelled" and cancelled["result"] is None
    before = lifecycle.snapshot(repository)
    with pytest.raises(ValueError):
        repository.update_job("owner", job["job_id"], status="completed", progress=100, stage="done", result={"quote": "resurrection"})
    with pytest.raises(WorkflowError):
        repository.save("owner", "one", "thread", stale)
    with repository._connect() as connection, pytest.raises(WorkflowError):
        repository._sync_resources(connection, "owner", "fresh", [source])
    assert lifecycle.snapshot(repository) == before
    restarted = UserSessionRepository(repository.database_path)
    with pytest.raises(WorkflowError):
        restarted.save("owner", "new", "thread", GraphState(resource_library=[source]))
    assert restarted.permanently_delete_source("owner", source.id, "owner")["deleted"]


def test_direct_removal_invalidates_and_stale_save_cannot_restore(tmp_path):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    state = populated(repository)
    stale = state.model_copy(deep=True)
    with repository._connect() as connection, pytest.raises(WorkflowError):
        repository._sync_resources(connection, "owner", "one", [])
    RemoveProjectResourceUseCase().execute(state, "source")
    repository.save("owner", "one", "thread", state)
    assert not state.messages and not state.presentation.state.presentation_validated
    assert repository.library_resource("owner", "source") is not None
    with pytest.raises(ConcurrentModificationError):
        repository.save("owner", "one", "thread", stale)


def test_delete_transaction_failure_rolls_back_all_copies_and_audit(tmp_path, monkeypatch):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    populated(repository)
    before = lifecycle.snapshot(repository)
    def fail(*args):
        raise RuntimeError("Synthetic injected failure")
    monkeypatch.setattr(repository, "_insert_event", fail)
    with pytest.raises(RuntimeError):
        repository.permanently_delete_source("owner", "source", "owner")
    assert lifecycle.snapshot(UserSessionRepository(repository.database_path)) == before


def test_delete_process_interruption_before_commit_rolls_back(tmp_path):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    populated(repository)
    before = lifecycle.snapshot(repository)
    script = """
import os, sys
from pathlib import Path
from app.interfaces.storage.user_session_repository import UserSessionRepository
repository = UserSessionRepository(Path(sys.argv[1]))
repository._insert_event = lambda *args: os._exit(73)
repository.permanently_delete_source('owner', 'source', 'owner')
"""
    result = subprocess.run([sys.executable, "-c", script, str(repository.database_path)], capture_output=True, timeout=30)
    assert result.returncode == 73, result.stderr.decode()
    assert lifecycle.snapshot(UserSessionRepository(repository.database_path)) == before


def test_cleanup_failure_is_pending_and_restart_retries_without_external_deletion(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    state = populated(repository)
    root = tmp_path / "exports"
    root.mkdir()
    internal = root / f"{state.presentation.id}-1234abcd.pptx"
    internal.write_bytes(b"Synthetic derived quote")
    external = tmp_path / "professor-copy.pptx"
    external.write_bytes(internal.read_bytes())
    unlink = Path.unlink
    def fail_internal(path, *args, **kwargs):
        if path.name == internal.name:
            raise PermissionError("Synthetic temporary failure")
        return unlink(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail_internal)
        result = repository.permanently_delete_source("owner", "source", "owner")
    assert result["cleanup_pending"] and internal.exists()
    assert repository.library_resource("owner", "source") is None
    restarted = UserSessionRepository(repository.database_path)
    assert not internal.exists() and external.read_bytes() == b"Synthetic derived quote"
    assert restarted.list_library_resources("owner") == []
    with restarted._connect() as connection:
        assert connection.execute("SELECT count(*) FROM source_cleanup").fetchone()[0] == 0


def test_project_deletion_keeps_library_and_removes_internal_exports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    state = populated(repository)
    Path("exports").mkdir()
    internal = Path("exports") / f"{state.presentation.id}-1234abcd.pptx"
    internal.write_bytes(b"synthetic deck")
    assert repository.delete_project("owner", "one")
    assert not internal.exists() and repository.load("owner", "one") is None
    assert repository.library_resource("owner", "source") is not None
    with pytest.raises(WorkflowError):
        repository.save("owner", "one", "thread", state)
    with pytest.raises(WorkflowError):
        repository.create_job("owner", "one", "slides")


def test_owner_library_api_cannot_cross_accounts(workspace):
    client, repository = workspace
    identifier = lifecycle.upload(client, pdf()).json()["resource_id"]
    token = client.post("/auth/register", json={"user_id": "second", "password": "synthetic-password"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/users/synthetic-owner/resources", headers=headers).status_code == 403
    assert client.delete(f"/users/synthetic-owner/resources/{identifier}", headers=headers).status_code == 403
    assert client.delete(f"/users/second/resources/{identifier}", headers=headers).status_code == 404
    response = client.delete(f"/users/synthetic-owner/resources/{identifier}")
    assert response.status_code == 200 and response.json()["deleted"]
    assert client.get("/users/synthetic-owner/resources").json() == {"resources": []}
    assert client.post(f"/projects/synthetic-owner/demo/library/{identifier}").status_code == 404


def test_delete_account_removes_owner_library(tmp_path):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    populated(repository)
    repository.delete_user("owner")
    assert repository.list_library_resources("owner") == []
    assert repository.load("owner", "one") is None


def test_ui_distinguishes_library_removal_and_permanent_deletion():
    script = Path("app/interfaces/web/app.js").read_text()
    for label in ("Retirer du projet", "Supprimer définitivement", "Ajouter au projet", "Remove from Project", "Delete permanently", "Add to Project"):
        assert label in script
    assert 'window.confirm' in script and 'result.cleanup_pending' in script
    assert 'current.status === "cancelled"' in script and 'sourceWorkCancelled' in script


def test_cleanup_does_not_follow_export_symlinks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    state = populated(repository)
    Path("exports").mkdir()
    external = tmp_path / "external.pptx"
    external.write_bytes(b"Professor copy")
    link = Path("exports") / f"{state.presentation.id}-1234abcd.pptx"
    link.symlink_to(external)
    assert not repository.permanently_delete_source("owner", "source", "owner")["cleanup_pending"]
    assert not link.is_symlink() and external.read_bytes() == b"Professor copy"


def test_cleanup_restart_uses_original_root_even_from_different_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    state = populated(repository)
    Path("exports").mkdir()
    internal = tmp_path / "exports" / f"{state.presentation.id}-1234abcd.pptx"
    internal.write_bytes(b"Synthetic export")
    monkeypatch.setattr(repository, "finish_source_cleanup", lambda: False)
    assert repository.permanently_delete_source("owner", "source", "owner")["cleanup_pending"]
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    restarted = UserSessionRepository(repository.database_path)
    assert not internal.exists() and not restarted.source_cleanup_pending()


def test_real_process_exit_after_commit_recovers_cleanup(tmp_path):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    populated(repository)
    script = """
import os, sys
from pathlib import Path
from app.interfaces.storage.user_session_repository import UserSessionRepository
repository = UserSessionRepository(Path(sys.argv[1]))
repository.finish_source_cleanup = lambda: os._exit(74)
repository.permanently_delete_source('owner', 'source', 'owner')
"""
    result = subprocess.run([sys.executable, "-c", script, str(repository.database_path)], capture_output=True, timeout=30)
    assert result.returncode == 74, result.stderr.decode()
    restarted = UserSessionRepository(repository.database_path)
    assert restarted.list_library_resources("owner") == []
    assert not restarted.load("owner", "one")[1].resource_library
    assert not restarted.source_cleanup_pending()
    with pytest.raises(WorkflowError):
        restarted.save("owner", "new", "thread", GraphState(resource_library=[read()]))


def test_library_collision_rejects_entire_direct_batch_without_writes(tmp_path):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    populated(repository)
    conflicting = read(pdf("Publication date: 2025"))
    fresh = read()
    fresh.id = "new-source"
    before = lifecycle.snapshot(repository)
    with repository._connect() as connection:
        with pytest.raises(WorkflowError):
            repository._sync_resources(connection, "owner", "other-project", [fresh, conflicting])
        assert connection.total_changes == 0
    assert lifecycle.snapshot(repository) == before


def test_additive_library_migration_keeps_historical_text_and_missing_original(tmp_path):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    state = populated(repository)
    with repository._connect() as connection:
        connection.execute("DELETE FROM owner_resources")
        connection.execute("UPDATE project_resources SET original_pdf = NULL")
    restarted = UserSessionRepository(repository.database_path)
    source = restarted.library_resource("owner", "source")
    assert source._original_content is None
    assert source.extracted_pages == state.resource_library[0].extracted_pages
    assert restarted.delete_project("owner", "one")
    assert restarted.library_resource("owner", "source") is not None


def test_export_failure_after_render_does_not_write_internal_files(workspace, monkeypatch, tmp_path):
    from app.interfaces.api import main as api
    from app.domain.enums.workflow_status import WorkflowStatus
    from io import BytesIO
    client, repository = workspace
    source = read()
    thread, state = repository.load("synthetic-owner", "demo")
    state.presentation = lifecycle.presentation([source])
    state.presentation.state.workflow_status = WorkflowStatus.READY_FOR_EXPORT
    state.resource_library = [source]
    repository.save("synthetic-owner", "demo", thread, state)
    files = set(tmp_path.rglob("*"))
    def stale_after_render(self, presentation, output, *args):
        assert isinstance(output, BytesIO)
        output.write(b"Synthetic generated deck")
        current_thread, current = repository.load("synthetic-owner", "demo")
        current.conversation_context.topic = "Newer human context"
        repository.save("synthetic-owner", "demo", current_thread, current)
    monkeypatch.setattr(api.ExportPowerPointUseCase, "execute", stale_after_render)
    response = client.get("/presentations/synthetic-owner/demo/export/pptx")
    assert response.status_code == 409
    assert set(tmp_path.rglob("*")) == files
    assert all(event["event_type"] != "PRESENTATION_EXPORTED" for event in repository.list_events("synthetic-owner", "demo"))


def test_busy_wal_checkpoint_reports_pending_then_recovers(tmp_path, monkeypatch):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    populated(repository)
    reader = repository._connect()
    reader.execute("BEGIN")
    reader.execute("SELECT * FROM owner_resources").fetchall()
    connect = repository._connect
    def short_timeout():
        connection = connect()
        connection.execute("PRAGMA busy_timeout = 1")
        return connection
    monkeypatch.setattr(repository, "_connect", short_timeout)
    try:
        result = repository.permanently_delete_source("owner", "source", "owner")
        assert result["cleanup_pending"]
        assert repository.list_library_resources("owner") == []
    finally:
        reader.close()
    restarted = UserSessionRepository(repository.database_path)
    assert not restarted.source_cleanup_pending()


def test_deleted_project_identifier_returns_conflict_instead_of_recreating(workspace):
    client, repository = workspace
    assert client.delete("/projects/synthetic-owner/demo").status_code == 204
    before = lifecycle.snapshot(repository)
    response = client.post("/projects", json={"user_id": "synthetic-owner", "project_id": "demo"})
    assert response.status_code == 409
    assert lifecycle.snapshot(repository) == before


def test_ambiguous_legacy_export_owner_refuses_without_touching_either_owner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    state = populated(repository)
    other = state.model_copy(deep=True)
    other.project_revision = 0
    repository.save("other", "copy", "thread", other)
    Path("exports").mkdir()
    internal = Path("exports") / f"{state.presentation.id}-1234abcd.pptx"
    internal.write_bytes(b"Ambiguous legacy owner")
    before = lifecycle.snapshot(repository)
    with pytest.raises(WorkflowError) as error:
        repository.permanently_delete_source("owner", "source", "owner")
    assert error.value.code == "EXPORT_OWNERSHIP_AMBIGUOUS"
    assert internal.read_bytes() == b"Ambiguous legacy owner"
    assert lifecycle.snapshot(repository) == before
    # No ambiguous internal file remains once its owner deliberately moves it.
    external = tmp_path / "professor-copy.pptx"
    internal.rename(external)
    assert repository.permanently_delete_source("owner", "source", "owner")["deleted"]
    assert repository.library_resource("other", "source") is not None
    assert external.read_bytes() == b"Ambiguous legacy owner"


@pytest.mark.parametrize("surface", ["missing_original", "forged_original", "metadata"])
def test_direct_owner_library_writer_cannot_bypass_screening(tmp_path, surface):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    resource = read()
    if surface == "missing_original":
        resource._original_content = None
    elif surface == "forged_original":
        resource._original_content = pdf("Publication date: 2025")
    else:
        resource.metadata.extensions["unsafe"] = "Patient ID: SYNTHETIC"
    before = lifecycle.snapshot(repository)
    with repository._connect() as connection:
        with pytest.raises(WorkflowError):
            repository._remember_source(connection, "owner", resource)
        assert connection.total_changes == 0
    assert lifecycle.snapshot(repository) == before
