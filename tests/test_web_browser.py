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
            expect(page.locator("#auth-role")).to_have_count(0)
            expect(page.locator("#auth-language option")).to_have_count(2)
            page.locator("#register").click()
            expect(page.locator("#setup-topic")).to_be_visible()
            expect(page.locator("#user-role")).to_have_count(0)
            expect(page.locator("#user-language option")).to_have_count(2)

            expect(page.locator("#project-evidence-settings")).to_contain_text("external")
            page.locator("#prototype-declaration").select_option("synthetic")
            page.locator("#prototype-acknowledged").check()
            page.locator('[data-action="declare-prototype"]').click()
            expect(page.locator("#prototype-acknowledged")).not_to_be_checked()
            expect(page.locator("#evidence-context-mode")).to_have_count(0)
            page.locator("#setup-topic").fill("Vitamin D clinical update")
            page.locator("#setup-objective").fill("Review only the evidence provided by the HCP.")
            page.locator("#setup-slides").fill("10")
            page.locator("#setup-instructions").fill("None")
            page.locator("#setup-scope").fill("Teaching public evidence within my specialty")
            page.locator("#setup-multidisciplinary").select_option("true")
            page.locator("#setup-scope-confirmed").check()
            page.locator("#setup-competence").check()
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


def test_owner_reviews_ocr_beside_original_before_generation(tmp_path, monkeypatch):
    """Real UI; synthetic OCR double. Screenshots are evidence only when executed."""
    if platform.system() == 'Darwin' and platform.mac_ver()[0].startswith('10.'):
        pytest.skip('Playwright Chromium requires macOS 12; OCR browser flow awaits supported CI.')
    import json
    from fastapi.testclient import TestClient
    from app.application.services.local_image_screening import LocalImageScreening, ImageInspection
    from app.application.services.source_document import SourceDocument
    from app.tests.test_raster_sources import synthetic_image
    repository = UserSessionRepository(tmp_path / 'ocr-browser.sqlite3')
    monkeypatch.setattr(api, 'get_repository', lambda: repository)
    monkeypatch.setattr(api, 'get_agent', lambda: pytest.fail('No external provider permitted'))
    result = ImageInspection(lines=[
        {'text': 'Synthetic teaching evidence', 'box': [0.1, 0.1, 0.9, 0.2], 'confidence': 0.99},
        {'text': 'Publication date: 2024', 'box': [0.1, 0.3, 0.9, 0.4], 'confidence': 0.99},
    ], faces=0)
    monkeypatch.setattr(LocalImageScreening, 'inspect', lambda content: result.model_copy(deep=True))
    token = TestClient(api.app).post('/auth/register', json={'user_id': 'ocr-owner', 'password': 'synthetic-password'}).json()['token']
    resource = SourceDocument.read('synthetic.png', synthetic_image(), 'synthetic')
    repository.save('ocr-owner', 'demo', 'thread', GraphState(prototype_declaration='synthetic', resource_library=[resource]))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            with _serve_fastapi_app() as base_url:
                page = browser.new_page()
                page.add_init_script('sessionStorage.setItem("hpa_user_id", "ocr-owner"); sessionStorage.setItem("hpa_token", ' + json.dumps(token) + ');')
                page.goto(base_url + '/app')
                page.locator('.workspace-tab[data-workspace="resources"]').click()
                page.locator('[data-resource-action="ocr-review"]').click()
                expect(page.locator('[data-ocr-save]')).to_be_disabled()
                page.wait_for_function('document.querySelector("[data-ocr-image]")?.naturalWidth > 0')
                page.locator('[data-ocr-confirm="0"]').check()
                page.locator('[data-ocr-confirm="1"]').check()
                page.locator('[data-ocr-value="0"]').fill('Synthetic corrected teaching evidence')
                expect(page.locator('[data-ocr-save]')).to_be_disabled()
                page.locator('[data-ocr-confirm="0"]').check()
                expect(page.locator('[data-ocr-save]')).to_be_enabled()
                page.screenshot(path=str(tmp_path / 'ocr-review.png'), full_page=True)
                page.locator('[data-ocr-save]').click()
                expect(page.locator('#ocr-review-panel')).to_be_hidden()
                expect(page.locator('#resource-list')).to_contain_text('user_confirmed')
                assert repository.library_resource('ocr-owner', 'synthetic').metadata.ocr_reviews[0].actor == 'ocr-owner'
        finally:
            browser.close()
