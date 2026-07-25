"""LangChain tool declarations; all business behavior lives in application use cases."""
from typing import Annotated

from langchain.tools import tool
from langchain_core.tools import InjectedToolArg

from app.ai.workflows.graph_state import GraphState
from app.application.use_cases.workflow_steps import (
    BuildBlueprintWorkflowUseCase, CollectPresentationContextUseCase,
    CreatePresentationWorkflowUseCase, GenerateSlidesWorkflowUseCase,
    ValidateFinalPresentationWorkflowUseCase, ValidateSlidesWorkflowUseCase,
    ValidateBlueprintWorkflowUseCase, ValidatePresentationContextUseCase,
    ValidateResourcesWorkflowUseCase,
)
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType


@tool
def collect_context(state: Annotated[GraphState, InjectedToolArg], topic: str | None = None, audience: AudienceType | None = None, presentation_type: PresentationType | None = None, language: Language | None = None, duration_minutes: int | None = None, objective: str | None = None) -> GraphState:
    """Store presentation details explicitly supplied by the user."""
    return CollectPresentationContextUseCase().execute(state, topic=topic, audience=audience, presentation_type=presentation_type, language=language, duration_minutes=duration_minutes, objective=objective)


@tool
def validate_context(state: Annotated[GraphState, InjectedToolArg]) -> GraphState:
    """Validate the collected presentation context."""
    return ValidatePresentationContextUseCase().execute(state)


@tool
def create_presentation(state: Annotated[GraphState, InjectedToolArg]) -> GraphState:
    """Create the presentation from the approved context."""
    return CreatePresentationWorkflowUseCase().execute(state)


@tool
def validate_resources(state: Annotated[GraphState, InjectedToolArg]) -> GraphState:
    """Validate uploaded evidence resources before blueprint generation."""
    return ValidateResourcesWorkflowUseCase().execute(state)


@tool
def build_blueprint(state: Annotated[GraphState, InjectedToolArg]) -> GraphState:
    """Generate a blueprint from validated resources."""
    return BuildBlueprintWorkflowUseCase().execute(state)


@tool
def validate_blueprint(state: Annotated[GraphState, InjectedToolArg], approved: bool) -> GraphState:
    """Record human approval of the generated blueprint."""
    return ValidateBlueprintWorkflowUseCase().execute(state, approved)


@tool
def generate_slides(state: Annotated[GraphState, InjectedToolArg]) -> GraphState:
    """Generate slides from the human-approved blueprint."""
    return GenerateSlidesWorkflowUseCase().execute(state)


@tool
def validate_slides(state: Annotated[GraphState, InjectedToolArg], approved: bool) -> GraphState:
    """Record human approval of all generated slides."""
    return ValidateSlidesWorkflowUseCase().execute(state, approved)


@tool
def validate_final_presentation(state: Annotated[GraphState, InjectedToolArg], approved: bool) -> GraphState:
    """Record the final human approval required before export."""
    return ValidateFinalPresentationWorkflowUseCase().execute(state, approved)


# The cognitive agent can advance production only. Human approvals are invoked
# directly by the interface/API and are deliberately not bound to the LLM.
COGNITIVE_TOOLS = (
    collect_context,
    validate_context,
    create_presentation,
    build_blueprint,
    generate_slides,
)

HUMAN_VALIDATION_TOOLS = (
    validate_resources,
    validate_blueprint,
    validate_slides,
    validate_final_presentation,
)

TOOLS = COGNITIVE_TOOLS + HUMAN_VALIDATION_TOOLS
