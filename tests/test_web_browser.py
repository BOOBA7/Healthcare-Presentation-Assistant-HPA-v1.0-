"""Focused browser test for the HCP path through the JavaScript web app.

The test starts the real FastAPI application and executes its HTTP routes from
Chromium. The two model boundaries are deterministic test doubles, so it never
uses an API key or external LLM. Browser binaries are installed in CI; a local
machine without Chromium skips this optional quality test with a clear reason.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import platform
import socket
import threading
import time

import fitz
import httpx
import pytest
from langchain_core.messages import AIMessage
from uvicorn import Config, Server

from app.ai.workflows.graph_state import GraphState
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.enums.workflow_step import WorkflowStep
from app.domain.models.agenda import Agenda
from app.domain.models.blueprint import Blueprint
from app.domain.models.execution_context import ExecutionContext
from app.domain.models.resource_analysis import ResourceAnalysis
from app.domain.models.slide_outline import SlideOutline
from app.interfaces.api import main as api
from app.interfaces.api.routers import jobs as job_routes
from app.interfaces.storage.user_session_repository import UserSessionRepository


playwright_sync_api = pytest.importorskip(
    "playwright.sync_api",
    reason="Playwright is an optional local browser-test dependency.",
)
PlaywrightError = playwright_sync_api.Error
expect = playwright_sync_api.expect
sync_playwright = playwright_sync_api.sync_playwright


class DeterministicBrowserBlueprint:
    """No-network model substitute for one blueprint generation job."""

    def execute(self, state: GraphState) -> GraphState:
        presentation = state.presentation
        assert presentation is not None
        presentation.blueprint = Blueprint(
            title=presentation.title,
            learning_objective=presentation.context.objective,
            target_number_of_slides=2,
            storytelling="Evidence first, then application.",
            sections=["Evidence", "Application"],
            slides=[
                SlideOutline(
                    slide_number=1,
                    title="Evidence overview",
                    objective="Introduce the supplied evidence.",
                    key_message="Keep claims within the uploaded PDF.",
                ),
                SlideOutline(
                    slide_number=2,
                    title="Clinical application",
                    objective="Discuss the intended context.",
                    key_message="Review evidence with the intended audience.",
                ),
            ],
        )
        presentation.agenda = Agenda(items=["Evidence overview", "Clinical application"])
        presentation.state.current_step = WorkflowStep.BLUEPRINT_VALIDATION
        presentation.state.workflow_status = WorkflowStatus.AWAITING_AGENDA_APPROVAL
        state.execution = ExecutionContext(last_tool="build_blueprint")
        state.messages.append(AIMessage(content="Deterministic blueprint ready for review."))
        return state


class DeterministicBrowserOverview:
    """No-network substitute for the Resource Overview model boundary."""

    def execute(self, resources, **kwargs) -> ResourceAnalysis:
        del kwargs
        resource = resources[0]
        return ResourceAnalysis(
            summary=(
                "The PDF supports a focused evidence discussion "
                f"[[cite: {resource.id} | p. 1 | Vitamin D evidence supplied by the HCP]]."
            ),
            resource_ids=[resource.id],
        )


def _write_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "Vitamin D evidence supplied by the HCP. This PDF is the sole source for the workflow test.",
    )
    document.save(path)
    document.close()


@contextmanager
def _serve_fastapi_app():
    """Run the ASGI app on a short-lived local port for a real browser test."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = Server(Config(api.app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{base_url}/api/v1/health", timeout=0.2).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=5)
        raise AssertionError("The local browser-test server did not start.")
    try:
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def test_hcp_can_upload_validate_analyze_and_generate_blueprint_in_browser(tmp_path, monkeypatch):
    """Protect the main HCP browser workflow against UI/event-handler regressions."""
    if platform.system() == "Darwin" and platform.mac_ver()[0].startswith("10."):
        pytest.skip("Playwright Chromium is not supported on macOS 10.15; CI runs this test on Ubuntu.")

    repository = UserSessionRepository(tmp_path / "browser.sqlite3")
    monkeypatch.setattr(api, "get_repository", lambda: repository)
    monkeypatch.setattr(api, "SummarizeResourcesUseCase", DeterministicBrowserOverview)
    monkeypatch.setattr(job_routes, "BuildBlueprintWorkflowUseCase", DeterministicBrowserBlueprint)

    pdf_path = tmp_path / "evidence.pdf"
    _write_pdf(pdf_path)

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except PlaywrightError as exc:
            pytest.skip(f"Playwright Chromium is not installed: {exc}")
        with _serve_fastapi_app() as base_url:
            page = browser.new_page()
            page.set_default_timeout(15_000)
            page.goto(f"{base_url}/app")

            page.locator("#auth-user-id").fill("browser-hcp")
            page.locator("#auth-password").fill("safe-local-password")
            page.locator("#register").click()
            expect(page.locator("#setup-topic")).to_be_visible()

            page.locator("#setup-topic").fill("Vitamin D clinical update")
            page.locator("#setup-objective").fill("Review only the evidence provided by the HCP.")
            page.locator("#presentation-setup-area details summary").click()
            page.locator("#setup-presenter-name").fill("Dr Ada Martin")
            page.locator("#setup-event-name").fill("HCP Evidence Update")
            page.locator("#presentation-setup-area [data-action='setup-presentation']").click()
            expect(page.locator("#presentation-title")).to_have_text("Vitamin D clinical update")

            page.locator(".workspace-tab[data-workspace='resources']").click()
            page.locator("#pdf-file").set_input_files(str(pdf_path))
            page.locator("#upload-resource").click()
            expect(page.locator("#resource-list")).to_contain_text("evidence.pdf")

            page.locator("#resource-list [data-resource-action='attach']").click()
            expect(page.locator("#resource-workflow-action [data-action='validate-resources']")).to_be_visible()
            page.locator("#resource-workflow-action [data-action='validate-resources']").click()
            expect(page.locator("#resource-workflow-action")).to_contain_text("validated")
            # The Resources workspace is a complete entry point for the
            # controlled production flow; the HCP does not need to discover
            # a second, hidden command in another workspace.
            expect(page.locator("#resource-workflow-action [data-action='resource-generate-blueprint']")).to_be_visible()

            page.locator("#analyze-resources").click()
            page.locator(".workspace-tab[data-workspace='analysis']").click()
            expect(page.locator("#resource-analysis-area")).to_contain_text("evidence.pdf")

            page.locator(".workspace-tab[data-workspace='resources']").click()
            page.locator("#resource-workflow-action [data-action='resource-generate-blueprint']").click()
            expect(page.locator("#agenda-area")).to_contain_text("Evidence overview")
            expect(page.locator("#review-area")).to_contain_text("Clinical application")
        browser.close()
