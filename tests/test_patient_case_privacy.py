import pytest
import fitz

from app.ai.workflows.graph_state import GraphState
from app.application.services.patient_case_privacy import PatientCasePrivacyGuard
from app.application.use_cases.extract_pdf_resource import ExtractPdfResourceUseCase
from app.application.use_cases.update_project_evidence_settings import UpdateProjectEvidenceSettingsUseCase
from app.domain.enums.evidence_context_mode import EvidenceContextMode
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.conversation_turn import ConversationTurn


def test_patient_case_guard_reports_categories_without_exposing_matched_value():
    with pytest.raises(WorkflowError) as caught:
        PatientCasePrivacyGuard().ensure_text_safe("Contact jane.doe@example.org before discussing the case.")

    assert caught.value.code == "PATIENT_IDENTIFIER_DETECTED"
    assert "email address" in caught.value.user_message
    assert "jane.doe@example.org" not in caught.value.user_message


def test_patient_case_mode_requires_acknowledgement_and_clean_existing_history():
    use_case = UpdateProjectEvidenceSettingsUseCase()
    with pytest.raises(WorkflowError, match="Confirm that all patient-case"):
        use_case.execute(
            GraphState(),
            evidence_context_mode=EvidenceContextMode.BM25,
            patient_case_mode=True,
            patient_case_acknowledged=False,
        )

    state = GraphState(
        conversation_history=[ConversationTurn(role="user", text="The patient email is jane.doe@example.org")]
    )
    with pytest.raises(WorkflowError) as caught:
        use_case.execute(
            state,
            evidence_context_mode=EvidenceContextMode.BM25,
            patient_case_mode=True,
            patient_case_acknowledged=True,
        )

    assert caught.value.code == "PATIENT_IDENTIFIER_DETECTED"


def test_patient_case_mode_can_be_enabled_for_a_deidentified_project():
    state = UpdateProjectEvidenceSettingsUseCase().execute(
        GraphState(),
        evidence_context_mode=EvidenceContextMode.DIRECT_BOUNDED,
        patient_case_mode=True,
        patient_case_acknowledged=True,
    )

    assert state.patient_case_mode is True
    assert state.patient_case_acknowledged is True
    assert state.evidence_context_mode == EvidenceContextMode.DIRECT_BOUNDED


def test_patient_case_mode_accepts_normal_scientific_pdf_dates_but_blocks_direct_identifiers():
    document = fitz.open()
    document.new_page().insert_text(
        (72, 72),
        "Clinical practice guideline published on 2024-01-31. Contact editor@example.org."
    )
    pdf_bytes = document.tobytes()
    document.close()

    with pytest.raises(WorkflowError) as caught:
        ExtractPdfResourceUseCase().execute("guideline.pdf", pdf_bytes, patient_case_mode=True)
    assert "email address" in caught.value.user_message

    document = fitz.open()
    document.new_page().insert_text((72, 72), "Clinical practice guideline published on 2024-01-31.")
    pdf_bytes = document.tobytes()
    document.close()

    resource = ExtractPdfResourceUseCase().execute("guideline.pdf", pdf_bytes, patient_case_mode=True)
    assert resource.title == "guideline.pdf"


def test_patient_case_mode_scans_existing_project_context_before_enablement():
    state = GraphState()
    state.conversation_context.topic = "Case admitted on 2024-01-31"

    with pytest.raises(WorkflowError) as caught:
        UpdateProjectEvidenceSettingsUseCase().execute(
            state,
            evidence_context_mode=EvidenceContextMode.BM25,
            patient_case_mode=True,
            patient_case_acknowledged=True,
        )

    assert caught.value.code == "PATIENT_IDENTIFIER_DETECTED"
