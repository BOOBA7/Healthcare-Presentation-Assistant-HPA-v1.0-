"""Human-controlled Project settings for evidence context and patient cases."""

from app.ai.workflows.graph_state import GraphState
from app.application.services.patient_case_privacy import PatientCasePrivacyGuard
from app.domain.enums.evidence_context_mode import EvidenceContextMode
from app.domain.exceptions.workflow_error import WorkflowError


class UpdateProjectEvidenceSettingsUseCase:
    """Persist settings without letting the LLM choose their safety boundary."""

    def execute(
        self,
        state: GraphState,
        *,
        evidence_context_mode: EvidenceContextMode,
        patient_case_mode: bool,
        patient_case_acknowledged: bool,
    ) -> GraphState:
        if patient_case_mode and not patient_case_acknowledged:
            raise WorkflowError(
                "PATIENT_CASE_ACKNOWLEDGEMENT_REQUIRED",
                "Confirm that all patient-case information is de-identified before enabling Patient Case Mode.",
            )
        if patient_case_mode:
            PatientCasePrivacyGuard().ensure_state_safe(state)

        if (
            state.presentation is not None
            and state.presentation.evidence_context_mode != evidence_context_mode
            and (state.presentation.blueprint is not None or state.presentation.slides)
        ):
            raise WorkflowError(
                "EVIDENCE_CONTEXT_CHANGE_REQUIRES_NEW_PROJECT",
                "Create a new Project to compare evidence-context modes after blueprint or slide generation has started.",
            )

        if state.evidence_context_mode != evidence_context_mode:
            # Existing overview text was produced from a different context
            # selection strategy. Do not present it as if it reflected the
            # newly selected experimental condition.
            state.resource_analysis = None
        state.evidence_context_mode = evidence_context_mode
        state.patient_case_mode = patient_case_mode
        state.patient_case_acknowledged = patient_case_mode and patient_case_acknowledged
        if state.presentation is not None:
            state.presentation.evidence_context_mode = evidence_context_mode
        return state
