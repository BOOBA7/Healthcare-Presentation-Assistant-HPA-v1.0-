"""Server-owned workflow view for deterministic presentation interfaces."""

from __future__ import annotations

from app.ai.workflows.graph_state import GraphState
from app.domain.enums.workflow_status import WorkflowStatus


class WorkflowViewBuilder:
    """Expose actionable workflow state without making the UI infer it."""

    @staticmethod
    def build(state: GraphState, active_job: dict[str, object] | None = None) -> dict[str, object]:
        presentation = state.presentation
        if presentation is None:
            return {
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
            allowed.append("generate_blueprint")
        elif status == WorkflowStatus.AWAITING_SCOPE_CLARIFICATION:
            blockers.append(
                WorkflowViewBuilder._blocker(
                    "PRESENTATION_SCOPE_CLARIFICATION_REQUIRED",
                    "scope_clarification",
                    "Explain the professional scope before generating the blueprint.",
                    ["clarify_professional_scope"],
                )
            )
        elif status == WorkflowStatus.AWAITING_AGENDA_APPROVAL:
            allowed.append("approve_agenda")
        elif status == WorkflowStatus.AWAITING_BLUEPRINT_APPROVAL:
            allowed.extend(["review_blueprint_items", "approve_blueprint"])
        elif status == WorkflowStatus.SLIDE_GENERATION:
            allowed.append("generate_slides")
        elif status == WorkflowStatus.AWAITING_SLIDE_RESOLUTION:
            blockers.append(
                WorkflowViewBuilder._blocker(
                    "INSUFFICIENT_EVIDENCE",
                    "slide_generation",
                    workflow.slide_generation_error
                    or "A slide cannot be generated from the selected validated PDFs.",
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

        return {
            "stage": status.value,
            "status": "running" if active_job else ("blocked" if blockers else "ready"),
            "allowed_actions": allowed,
            "blockers": blockers,
            "active_job": active_job,
            "progress": {
                "resources_selected": len(presentation.resources),
                "resources_validated": workflow.resources_validated,
                "blueprint_generated": presentation.blueprint is not None,
                "agenda_validated": bool(presentation.agenda and presentation.agenda.is_validated),
                "blueprint_validated": workflow.blueprint_validated,
                "slides_generated": len(presentation.slides),
                "slides_validated": workflow.slides_validated,
                "presentation_validated": workflow.presentation_validated,
            },
        }

    @staticmethod
    def _blocker(
        code: str,
        stage: str,
        message: str,
        next_actions: list[str],
        *,
        item_number: int | None = None,
        retryable: bool = False,
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
