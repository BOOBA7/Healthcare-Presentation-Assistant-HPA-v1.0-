import pytest
import fitz

from app.ai.workflows.graph_state import GraphState
from app.application.services.patient_case_privacy import PatientCasePrivacyGuard
from app.application.use_cases.extract_pdf_resource import ExtractPdfResourceUseCase
from app.application.use_cases.update_project_evidence_settings import UpdateProjectEvidenceSettingsUseCase
from app.domain.enums.evidence_context_mode import EvidenceContextMode
from app.domain.exceptions.workflow_error import WorkflowError


def test_patient_case_guard_reports_categories_without_exposing_matched_value():
    with pytest.raises(WorkflowError) as caught:
        PatientCasePrivacyGuard().ensure_text_safe("Contact jane.doe@example.org before discussing the case.")

    assert caught.value.code == "PATIENT_IDENTIFIER_DETECTED"
    assert "email address" in caught.value.user_message
    assert "jane.doe@example.org" not in caught.value.user_message


@pytest.mark.parametrize("acknowledged", [False, True])
def test_prototype_refuses_patient_cases_even_with_acknowledgement(acknowledged):
    state = GraphState(prototype_declaration="synthetic")
    with pytest.raises(WorkflowError) as caught:
        UpdateProjectEvidenceSettingsUseCase().execute(
            state, evidence_context_mode=EvidenceContextMode.BM25,
            patient_case_mode=True, patient_case_acknowledged=acknowledged,
        )
    assert caught.value.code == "PROTOTYPE_DECLARATION_REQUIRED"
    assert state.patient_case_mode is False


def test_public_pdf_dates_are_allowed_but_patient_mode_is_refused():
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Clinical practice guideline published on 2024-01-31.")
    document[0].insert_text((72, 40), "Publication date: 2024")
    pdf_bytes = document.tobytes()
    document.close()
    with pytest.raises(WorkflowError):
        ExtractPdfResourceUseCase().execute(
            "guideline.pdf", pdf_bytes, patient_case_mode=True, prototype_declaration="synthetic",
        )
    resource = ExtractPdfResourceUseCase().execute(
        "guideline.pdf", pdf_bytes, prototype_declaration="synthetic",
    )
    assert resource.title == "guideline.pdf"


def test_identifier_detector_still_screens_existing_context():
    state = GraphState()
    state.conversation_context.topic = "Case admitted on 2024-01-31"
    with pytest.raises(WorkflowError) as caught:
        PatientCasePrivacyGuard().ensure_state_safe(state)
    assert caught.value.code == "PATIENT_IDENTIFIER_DETECTED"
