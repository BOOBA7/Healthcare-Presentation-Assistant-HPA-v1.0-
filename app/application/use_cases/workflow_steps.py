"""State-based workflow use cases used exclusively by HPA business tools."""

from app.ai.workflows.graph_state import GraphState
from app.application.use_cases.build_blueprint import BuildBlueprintUseCase
from app.application.use_cases.create_presentation import CreatePresentationUseCase
from app.application.use_cases.generate_slides import GenerateSlidesUseCase
from app.application.use_cases.validate_resources import ValidateResourcesUseCase
from app.application.validators.audience_validator import AudienceValidator
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.models.conversation_context import ConversationContext
from app.domain.value_objects.presentation_context import PresentationContext


class CollectPresentationContextUseCase:
    def execute(self, state: GraphState, **updates: object) -> GraphState:
        allowed = {"topic", "audience", "presentation_type", "language", "duration_minutes", "objective"}
        values = {key: value for key, value in updates.items() if key in allowed and value is not None}
        context = ConversationContext.model_validate({**state.conversation_context.model_dump(), **values})
        return state.model_copy(update={"conversation_context": context})


class ValidatePresentationContextUseCase:
    def execute(self, state: GraphState) -> GraphState:
        context = state.conversation_context
        if not context.is_complete():
            raise ValueError(f"Missing context fields: {', '.join(context.missing_fields())}")
        is_valid, messages = AudienceValidator().validate(context.audience)
        if not is_valid:
            raise ValueError("; ".join(messages))
        return state.model_copy(update={"presentation_context": PresentationContext(**context.model_dump())})


class CreatePresentationWorkflowUseCase:
    def execute(self, state: GraphState) -> GraphState:
        if state.presentation is not None:
            return state
        if state.presentation_context is None:
            raise ValueError("Validate the context before creating the presentation.")
        presentation = CreatePresentationUseCase().execute(state.presentation_context.topic, state.presentation_context)
        return state.model_copy(update={"presentation": presentation})


class ValidateResourcesWorkflowUseCase:
    def execute(self, state: GraphState) -> GraphState:
        if state.presentation is None:
            raise ValueError("Create the presentation before validating resources.")
        presentation = ValidateResourcesUseCase().execute(state.presentation)
        return state.model_copy(update={"presentation": presentation})


class BuildBlueprintWorkflowUseCase:
    def execute(self, state: GraphState) -> GraphState:
        if state.presentation is None:
            raise ValueError("Create the presentation before generating its blueprint.")
        if not state.presentation.state.resources_validated:
            raise ValueError("Validate uploaded resources before generating the blueprint.")
        presentation = BuildBlueprintUseCase().execute(state.presentation)
        return state.model_copy(update={"presentation": presentation})


class ValidateBlueprintWorkflowUseCase:
    def execute(self, state: GraphState, approved: bool) -> GraphState:
        if state.presentation is None or state.presentation.blueprint is None:
            raise ValueError("Generate a blueprint before validating it.")
        if not approved:
            raise ValueError("Blueprint was not approved by the human reviewer.")
        state.presentation.blueprint.is_validated = True
        state.presentation.state.blueprint_validated = True
        return state


class GenerateSlidesWorkflowUseCase:
    def execute(self, state: GraphState) -> GraphState:
        if state.presentation is None or not state.presentation.state.blueprint_validated:
            raise ValueError("Validate the blueprint before generating slides.")
        presentation = GenerateSlidesUseCase().execute(state.presentation)
        return state.model_copy(update={"presentation": presentation})


class ValidateSlidesWorkflowUseCase:
    def execute(self, state: GraphState, approved: bool) -> GraphState:
        if state.presentation is None or not state.presentation.slides:
            raise ValueError("Generate slides before validating them.")
        if not approved:
            raise ValueError("Slides were not approved by the human reviewer.")
        state.presentation.state.slides_validated = True
        return state


class ValidateFinalPresentationWorkflowUseCase:
    def execute(self, state: GraphState, approved: bool) -> GraphState:
        if state.presentation is None or not state.presentation.state.slides_validated:
            raise ValueError("Validate slides before approving the final presentation.")
        if not approved:
            raise ValueError("Final presentation was not approved by the human reviewer.")
        state.presentation.state.presentation_validated = True
        return state
