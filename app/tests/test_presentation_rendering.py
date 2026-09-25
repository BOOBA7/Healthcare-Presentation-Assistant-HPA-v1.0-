from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired

import pytest

from app.application.services.presentation_rendering import LocalPresentationRenderer, find_soffice
from app.domain.exceptions.workflow_error import WorkflowError


def test_missing_renderer_has_stable_error(monkeypatch):
    monkeypatch.setattr("app.application.services.presentation_rendering.shutil.which", lambda _: None)
    monkeypatch.setattr(Path, "is_file", lambda self: False)

    with pytest.raises(WorkflowError) as raised:
        find_soffice()

    assert raised.value.code == "PRESENTATION_RENDERER_UNAVAILABLE"


def test_renderer_uses_isolated_profile_and_preserves_existing_destination(tmp_path, monkeypatch):
    source = tmp_path / "fixture.pptx"
    destination = tmp_path / "fixture.pdf"
    source.write_bytes(b"synthetic pptx placeholder")
    destination.write_bytes(b"existing external copy")
    calls = []

    def convert(command, **kwargs):
        calls.append((command, kwargs))
        output_dir = Path(command[command.index("--outdir") + 1])
        (output_dir / "fixture.pdf").write_bytes(b"%PDF-1.7 synthetic")
        return CompletedProcess(command, 0)

    monkeypatch.setattr("app.application.services.presentation_rendering.subprocess.run", convert)
    with pytest.raises(WorkflowError) as raised:
        LocalPresentationRenderer(Path("/synthetic/soffice")).render_pdf(source, destination)

    assert raised.value.code == "PRESENTATION_RENDER_DESTINATION_EXISTS"
    assert destination.read_bytes() == b"existing external copy"
    assert calls[0][0][1].startswith("-env:UserInstallation=file://")
    assert calls[0][1]["timeout"] == 120


def test_renderer_reports_timeout_without_output(tmp_path, monkeypatch):
    source = tmp_path / "fixture.pptx"
    source.write_bytes(b"synthetic pptx placeholder")

    def timeout(command, **kwargs):
        raise TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr("app.application.services.presentation_rendering.subprocess.run", timeout)
    with pytest.raises(WorkflowError) as raised:
        LocalPresentationRenderer(Path("/synthetic/soffice")).render_pdf(source, tmp_path / "fixture.pdf")

    assert raised.value.code == "PRESENTATION_RENDER_TIMEOUT"
