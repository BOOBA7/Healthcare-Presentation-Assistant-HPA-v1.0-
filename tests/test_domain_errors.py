import pytest

from app.application.services.workflow_policy import WorkflowPolicy
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.exceptions import DomainError, InvalidTransition, ValidationError, WorkflowError


def test_domain_exception_hierarchy_preserves_value_error_compatibility():
    error = WorkflowError("RESOURCE_NOT_FOUND", "Resource not found.")

    assert isinstance(error, DomainError)
    assert isinstance(error, ValueError)
    assert error.code == "RESOURCE_NOT_FOUND"


def test_invalid_transition_is_a_specialized_workflow_error():
    with pytest.raises(InvalidTransition) as caught:
        WorkflowPolicy.require_status(
            WorkflowStatus.AWAITING_RESOURCE_UPLOAD,
            (WorkflowStatus.BLUEPRINT_GENERATION,),
            "generate a blueprint",
        )

    assert isinstance(caught.value, WorkflowError)
    assert caught.value.code == "INVALID_WORKFLOW_TRANSITION"


def test_validation_error_has_a_stable_default_code():
    error = ValidationError("A citation is invalid.")

    assert isinstance(error, DomainError)
    assert error.code == "DOMAIN_VALIDATION_FAILED"
