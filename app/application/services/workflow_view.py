"""Server-owned workflow view for deterministic presentation interfaces."""

from __future__ import annotations

from app.application.services.presentation_context_policy import PresentationContextPolicy
from app.application.services.source_date_policy import SourceDatePolicy
from app.application.services.resource_library import resolve_presentation_resources
from app.domain.exceptions.domain_error import DomainError
from app.ai.workflows.graph_state import GraphState
from app.domain.enums.workflow_status import WorkflowStatus
from app.application.services.evidence_coverage import EvidenceCoverageService


class WorkflowViewBuilder:
    """Expose actionable workflow state without making the UI infer it."""

    @staticmethod
    def build(state: GraphState, active_job: dict[str, object] | None = None) -> dict[str, object]:
        presentation = state.presentation
        if presentation is None:
            response = {
                "stage": WorkflowStatus.CONTEXT_COLLECTION.value,
                "status": "blocked",
                "allowed_actions": ["setup_presentation"],
                "blockers": [
                    WorkflowViewBuilder._blocker(
                        "PRESENTATION_SETUP_REQUIRED",
                        "presentation_setup",
                        "Create the presentation from the human-controlled setup form before selecting production evidence.",
                        ["setup_presentation"],
                    )
                ],
                "active_job": active_job,
            }
            response["next_action"] = WorkflowViewBuilder._next_action(
                response["allowed_actions"], response["blockers"], active_job
            )
            return response

        try:
            PresentationContextPolicy.require(presentation)
        except ValueError as exc:
            response = {"stage": "context_collection", "status": "blocked",
                    "allowed_actions": ["setup_presentation"], "active_job": active_job,
                    "blockers": [WorkflowViewBuilder._blocker(
                        "PRESENTATION_CONTEXT_REQUIRED", "presentation_setup", str(exc), ["setup_presentation"])]}
            response["next_action"] = WorkflowViewBuilder._next_action(
                response["allowed_actions"], response["blockers"], active_job
            )
            return response

        try:
            SourceDatePolicy.require_all(resolve_presentation_resources(state))
        except DomainError as exc:
            response = {"stage": presentation.state.workflow_status.value, "status": "blocked",
                        "allowed_actions": ["replace_resource"], "active_job": active_job,
                        "blockers": [WorkflowViewBuilder._blocker(exc.code, "evidence_selection", exc.user_message, ["replace_resource"])]}
            response["next_action"] = WorkflowViewBuilder._next_action(response["allowed_actions"], response["blockers"], active_job)
            return response

        workflow = presentation.state
        status = workflow.workflow_status
        allowed: list[str] = []
        blockers: list[dict[str, object]] = []

        if status == WorkflowStatus.AWAITING_RESOURCE_UPLOAD:
            blockers.append(
                WorkflowViewBuilder._blocker(
                    "RESOURCE_SELECTION_REQUIRED",
                    "evidence_selection",
                    "Select at least one uploaded PDF for this presentation.",
                    ["select_resource"],
                )
            )
        elif status == WorkflowStatus.AWAITING_RESOURCE_VALIDATION:
            allowed.append("validate_resources")
        elif status == WorkflowStatus.BLUEPRINT_GENERATION:
            coverage = presentation.evidence_coverage
            if coverage is None or not EvidenceCoverageService().is_current(
                coverage, presentation, resolve_presentation_resources(state), state.resource_chunks
            ):
                allowed.append("assess_evidence_coverage")
            elif not coverage.sufficient:
                blockers.append(WorkflowViewBuilder._blocker(
                    "EVIDENCE_COVERAGE_INSUFFICIENT", "evidence_coverage",
                    "Resolve every missing evidence area before creating the Agenda.",
                    ["add_resource", "change_context", "reassess_evidence_coverage"],
                    diagnostic={"dimensions": [result.model_dump(mode="json") for result in coverage.results]},
                ))
                allowed.append("assess_evidence_coverage")
            elif presentation.agenda is None:
                allowed.append("generate_agenda")
            elif presentation.agenda.is_validated:
                allowed.append("generate_blueprint")
        elif status == WorkflowStatus.AWAITING_SCOPE_CLARIFICATION:
            blockers.append(
                WorkflowViewBuilder._blocker(
                    "PRESENTATION_SCOPE_CLARIFICATION_REQUIRED",
                    "scope_clarification",
                    "Complete the Professional scope form before generating the blueprint.",
                    ["clarify_professional_scope"],
                )
            )
        elif status == WorkflowStatus.AWAITING_AGENDA_APPROVAL:
            allowed.extend(["edit_agenda", "approve_agenda"])
        elif status == WorkflowStatus.AWAITING_BLUEPRINT_APPROVAL:
            allowed.extend(["review_blueprint_items", "approve_blueprint"])
        elif status == WorkflowStatus.SLIDE_GENERATION:
            allowed.append("generate_slides")
        elif status == WorkflowStatus.AWAITING_SLIDE_RESOLUTION:
            allowed.append("review_slides")
            for slide_blocker in workflow.slide_generation_blockers:
                actions = ["edit_blueprint_item", "attach_resource", "write_slide_as_user"]
                if slide_blocker.code == "INVALID_AI_PROVENANCE":
                    actions.append("retry_slide_generation")
                blockers.append(
                    WorkflowViewBuilder._blocker(
                        slide_blocker.code,
                        "slide_generation",
                        slide_blocker.message,
                        actions,
                        item_number=slide_blocker.slide_number,
                        diagnostic=slide_blocker.diagnostic,
                    )
                )
            if not blockers:
                blockers.append(
                    WorkflowViewBuilder._blocker(
                        "SLIDE_RESOLUTION_REQUIRED",
                        "slide_generation",
                        workflow.slide_generation_error
                        or "A slide must be resolved before the complete set can be approved.",
                        ["edit_blueprint_item", "attach_resource", "write_slide_as_user"],
                        item_number=workflow.blocked_slide_number,
                    )
                )
        elif status == WorkflowStatus.AWAITING_SLIDE_APPROVAL:
            allowed.extend(["review_slides", "approve_slides"])
        elif status == WorkflowStatus.AWAITING_FINAL_APPROVAL:
            allowed.append("approve_final_presentation")
        elif status in {WorkflowStatus.READY_FOR_EXPORT, WorkflowStatus.EXPORTED}:
            allowed.append("export_powerpoint")

        error = WorkflowViewBuilder._last_error(state)
        if error:
            blockers.append(error)

        response = {
            "stage": status.value,
            "status": "running" if active_job else ("blocked" if blockers else "ready"),
            "allowed_actions": allowed,
            "blockers": blockers,
            "active_job": active_job,
            "progress": {
                "resources_selected": len(presentation.resources),
                "resources_validated": workflow.resources_validated,
                "evidence_coverage_sufficient": bool(presentation.evidence_coverage and presentation.evidence_coverage.sufficient),
                "blueprint_generated": presentation.blueprint is not None,
                "agenda_validated": bool(presentation.agenda and presentation.agenda.is_validated),
                "blueprint_validated": workflow.blueprint_validated,
                "slides_generated": len(presentation.slides),
                "slides_expected": len(presentation.blueprint.slides) if presentation.blueprint else 0,
                "slides_blocked": len(workflow.slide_generation_blockers),
                "slides_validated": workflow.slides_validated,
                "presentation_validated": workflow.presentation_validated,
            },
        }
        response["next_action"] = WorkflowViewBuilder._next_action(allowed, blockers, active_job)
        return response

    @staticmethod
    def _next_action(
        allowed_actions: list[str], blockers: list[dict[str, object]], active_job: dict[str, object] | None
    ) -> dict[str, object]:
        """Select the server-owned next step; the browser must not infer workflow order."""
        if active_job:
            return {
                "action": "wait_for_active_job",
                "message": "Wait for the active operation to finish before taking another workflow action.",
            }
        if blockers:
            blocker = blockers[0]
            actions = blocker.get("next_actions", [])
            action = actions[0] if actions else "resolve_blocker"
            return {
                "action": action,
                "message": blocker.get("message", "Resolve the workflow blocker before continuing."),
                "blocker_code": blocker.get("code"),
            }
        if allowed_actions:
            return {"action": allowed_actions[0]}
        return {"action": "review_workflow"}

    @staticmethod
    def _blocker(
        code: str,
        stage: str,
        message: str,
        next_actions: list[str],
        *,
        item_number: int | None = None,
        retryable: bool = False,
        diagnostic: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": code,
            "category": "business_blocker",
            "stage": stage,
            "message": message,
            "next_actions": next_actions,
            "recoverable": True,
        }
        if item_number is not None:
            payload["item_number"] = item_number
        if retryable:
            payload["category"] = "job_failure"
            payload["recoverable"] = True
        if diagnostic:
            payload["diagnostic"] = diagnostic
        return payload

    @staticmethod
    def _last_error(state: GraphState) -> dict[str, object] | None:
        execution = state.execution
        output = execution.tool_output if isinstance(execution.tool_output, dict) else {}
        code = output.get("error_code") if isinstance(output.get("error_code"), str) else None
        if not code or code in {"RESOURCES_VALIDATION_REQUIRED", "INSUFFICIENT_EVIDENCE"}:
            return None
        message = execution.error or "The last workflow operation could not be completed."
        return WorkflowViewBuilder._blocker(
            code,
            "workflow_operation",
            message,
            ["retry"],
            retryable=bool(output.get("retryable")),
        )
