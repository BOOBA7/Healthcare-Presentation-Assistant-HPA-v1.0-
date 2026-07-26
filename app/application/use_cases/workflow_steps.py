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
        presentation = CreatePresentationUseCase().execute(
            state.presentation_context.topic,
            state.presentation_context,
            state.user_profile,
        )
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
        if state.presentation.agenda is None or not state.presentation.agenda.is_validated:
            raise ValueError("Review and approve the proposed agenda before approving the blueprint.")
        if not all(outline.is_validated for outline in state.presentation.blueprint.slides):
            raise ValueError("Approve every blueprint item before approving the complete blueprint.")
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
        if not all(slide.is_validated for slide in state.presentation.slides):
            raise ValueError("Approve every slide before approving all slides.")
        state.presentation.state.slides_validated = True
        return state


class ReviewBlueprintItemUseCase:
    def execute(self, state: GraphState, index: int, comments: str | None) -> GraphState:
        if state.presentation is None or state.presentation.blueprint is None:
            raise ValueError("Generate a blueprint before reviewing it.")
        outlines = state.presentation.blueprint.slides
        if not 0 <= index < len(outlines):
            raise ValueError("Blueprint item index is invalid.")
        outlines[index].is_validated = True
        outlines[index].reviewer_comments = comments.strip() or None if comments else None
        return state


class ReviewSlideUseCase:
    def execute(self, state: GraphState, index: int, comments: str | None) -> GraphState:
        if state.presentation is None or not state.presentation.slides:
            raise ValueError("Generate slides before reviewing them.")
        if not 0 <= index < len(state.presentation.slides):
            raise ValueError("Slide index is invalid.")
        slide = state.presentation.slides[index]
        slide.is_validated = True
        slide.reviewer_comments = comments.strip() or None if comments else None
        return state


class RejectBlueprintItemUseCase:
    def execute(self, state: GraphState, index: int, comments: str) -> GraphState:
        if state.presentation is None or state.presentation.blueprint is None:
            raise ValueError("Generate a blueprint before reviewing it.")
        if not 0 <= index < len(state.presentation.blueprint.slides):
            raise ValueError("Blueprint item index is invalid.")
        item = state.presentation.blueprint.slides[index]
        item.is_validated = False
        item.reviewer_comments = comments.strip() or "Revision requested by reviewer."
        state.presentation.blueprint.is_validated = False
        state.presentation.state.blueprint_validated = False
        return state


class RejectSlideUseCase:
    def execute(self, state: GraphState, index: int, comments: str) -> GraphState:
        if state.presentation is None or not state.presentation.slides:
            raise ValueError("Generate slides before reviewing them.")
        if not 0 <= index < len(state.presentation.slides):
            raise ValueError("Slide index is invalid.")
        slide = state.presentation.slides[index]
        slide.is_validated = False
        slide.reviewer_comments = comments.strip() or "Revision requested by reviewer."
        state.presentation.state.slides_validated = False
        state.presentation.state.presentation_validated = False
        return state


class RegenerateBlueprintUseCase:
    def execute(self, state: GraphState) -> GraphState:
        if state.presentation is None or state.presentation.blueprint is None:
            raise ValueError("Generate a blueprint before requesting revisions.")
        presentation = BuildBlueprintUseCase().execute(state.presentation)
        presentation.state.blueprint_validated = False
        presentation.state.slides_validated = False
        presentation.state.presentation_validated = False
        return state.model_copy(update={"presentation": presentation})


class RegenerateSlideUseCase:
    def execute(self, state: GraphState, index: int) -> GraphState:
        if state.presentation is None or state.presentation.blueprint is None:
            raise ValueError("Generate a blueprint before regenerating a slide.")
        if not 0 <= index < len(state.presentation.slides):
            raise ValueError("Slide index is invalid.")
        from app.ai.chains.slide_chain import SlideChain
        from app.ai.mappers.slide_mapper import SlideMapper
        from app.application.validators.evidence_provenance_validator import EvidenceProvenanceValidator

        replacement = SlideMapper().to_domain(
            SlideChain().invoke(state.presentation, state.presentation.blueprint.slides[index])
        )
        EvidenceProvenanceValidator().validate_slide(replacement, state.presentation.resources)
        replacement.reviewer_comments = state.presentation.slides[index].reviewer_comments
        state.presentation.slides[index] = replacement
        state.presentation.state.slides_validated = False
        state.presentation.state.presentation_validated = False
        return state


class ValidateFinalPresentationWorkflowUseCase:
    def execute(self, state: GraphState, approved: bool) -> GraphState:
        if state.presentation is None or not state.presentation.state.slides_validated:
            raise ValueError("Validate slides before approving the final presentation.")
        if not approved:
            raise ValueError("Final presentation was not approved by the human reviewer.")
        state.presentation.state.presentation_validated = True
        return state
