"""Local PPTX-to-PDF rendering adapter for the macOS prototype.

The editable PPTX is the single render source. LibreOffice is deliberately an
OS dependency rather than a Python dependency: on macOS its headless executable
is normally ``/Applications/LibreOffice.app/Contents/MacOS/soffice``. The same
adapter also accepts a ``soffice`` found on PATH.

Expected fidelity is suitable for review of slide order, text, images, common
charts/tables and gross clipping or overlap. It is not pixel-identical to
PowerPoint: substituted fonts, animations, media, SmartArt, uncommon effects,
and some uploaded-template features can render differently. PDF is intentionally
not editable and speaker notes are not represented in its slide pages.

This low-level adapter does not decide whether export is authorised. Production
callers must retain the existing deterministic workflow, approval, evidence,
privacy, provenance and revision/concurrency gates before supplying a PPTX.
Each conversion uses private temporary output and profile directories so
parallel jobs do not share LibreOffice state or expose intermediate artefacts.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from app.domain.exceptions.workflow_error import WorkflowError


_MACOS_SOFFICE = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")


def find_soffice() -> Path:
    """Return the local LibreOffice executable or a stable unavailable error."""
    command = shutil.which("soffice") or shutil.which("libreoffice")
    if command:
        return Path(command)
    if _MACOS_SOFFICE.is_file():
        return _MACOS_SOFFICE
    raise WorkflowError(
        "PRESENTATION_RENDERER_UNAVAILABLE",
        "LibreOffice is required for local PDF rendering but was not found. "
        "Install the macOS LibreOffice application or place soffice on PATH.",
    )


class LocalPresentationRenderer:
    """Convert an existing PPTX to PDF without a shell or shared user profile."""

    def __init__(self, executable: Path | None = None, *, timeout_seconds: int = 120) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    def render_pdf(self, pptx_path: Path, destination: Path) -> Path:
        source = pptx_path.resolve()
        if source.suffix.lower() != ".pptx" or not source.is_file():
            raise WorkflowError(
                "PRESENTATION_RENDER_SOURCE_INVALID",
                "A readable PPTX source is required for local PDF rendering.",
            )
        if destination.suffix.lower() != ".pdf":
            raise WorkflowError(
                "PRESENTATION_RENDER_DESTINATION_INVALID",
                "The local presentation render destination must be a PDF file.",
            )
        executable = self.executable or find_soffice()
        with TemporaryDirectory(prefix="hpa-render-") as temporary:
            workspace = Path(temporary)
            output_dir = workspace / "output"
            profile_dir = workspace / "profile"
            output_dir.mkdir()
            profile_dir.mkdir()
            command = [
                str(executable),
                f"-env:UserInstallation={profile_dir.as_uri()}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(source),
            ]
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    check=False,
                    timeout=self.timeout_seconds,
                )
            except FileNotFoundError as exc:
                raise WorkflowError(
                    "PRESENTATION_RENDERER_UNAVAILABLE",
                    "The configured LibreOffice executable is unavailable.",
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise WorkflowError(
                    "PRESENTATION_RENDER_TIMEOUT",
                    "Local PDF rendering timed out.",
                    retryable=True,
                ) from exc
            rendered = output_dir / f"{source.stem}.pdf"
            if completed.returncode or not rendered.is_file() or rendered.stat().st_size == 0:
                raise WorkflowError(
                    "PRESENTATION_RENDER_FAILED",
                    "LibreOffice could not render the presentation as PDF.",
                    retryable=True,
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise WorkflowError(
                    "PRESENTATION_RENDER_DESTINATION_EXISTS",
                    "The PDF destination already exists and was left untouched.",
                )
            shutil.copyfile(rendered, destination)
        return destination
