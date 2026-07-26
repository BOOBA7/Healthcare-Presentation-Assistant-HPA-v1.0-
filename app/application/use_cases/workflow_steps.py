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
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.exceptions.workflow_error import WorkflowError
from app.application.services.workflow_policy import WorkflowPolicy
from app.application.services.production_evidence_gate import ProductionEvidenceGate
from app.application.validators.presentation_compatibility_validator import PresentationCompatibilityValidator


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
            raise WorkflowError("CONTEXT_NOT_VALIDATED", "Validate the context before creating the presentation.")
        presentation = CreatePresentationUseCase().execute(
            state.presentation_context.topic,
            state.presentation_context,
            state.user_profile,
        )
        return state.model_copy(update={"presentation": presentation})


class ValidateResourcesWorkflowUseCase:
    def execute(self, state: GraphState) -> GraphState:
        if state.presentation is None:
            raise WorkflowError("PRESENTATION_NOT_CREATED", "Create the presentation before validating resources.")
        presentation = ValidateResourcesUseCase().execute(state.presentation)
        return state.model_copy(update={"presentation": presentation})


class BuildBlueprintWorkflowUseCase:
    def execute(self, state: GraphState) -> GraphState:
        if state.presentation is None:
            raise WorkflowError("PRESENTATION_NOT_CREATED", "Create the presentation before generating its blueprint.")
        if not state.presentation.state.resources_validated:
            raise WorkflowError("RESOURCES_NOT_VALIDATED", "Validate uploaded resources before generating the blueprint.")
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.BLUEPRINT_GENERATION,),
            "generate the blueprint",
        )
        clarification = PresentationCompatibilityValidator().clarification_message(state.presentation)
        if clarification:
            state.presentation.state.workflow_status = WorkflowStatus.AWAITING_SCOPE_CLARIFICATION
            raise WorkflowError("PRESENTATION_SCOPE_CLARIFICATION_REQUIRED", clarification)
        presentation = BuildBlueprintUseCase().execute(state.presentation)
        return state.model_copy(update={"presentation": presentation})


class RecordProfessionalScopeUseCase:
    """Persist the user's explanation for a detected profile/audience mismatch."""

    def execute(self, state: GraphState, explanation: str) -> GraphState:
        if state.presentation is None:
            raise WorkflowError("PRESENTATION_NOT_CREATED", "Create the presentation before clarifying its scope.")
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.AWAITING_SCOPE_CLARIFICATION,),
            "clarify the professional scope",
        )
        normalized = explanation.strip()
        if len(normalized) < 12:
            raise WorkflowError(
                "SCOPE_EXPLANATION_TOO_SHORT",
                "Explain your role and why this audience and topic are within your presentation scope.",
            )
        state.presentation.professional_scope = normalized
        state.presentation.state.workflow_status = (
            WorkflowStatus.SLIDE_GENERATION
            if state.presentation.state.blueprint_validated
            else WorkflowStatus.BLUEPRINT_GENERATION
        )
        return state


class ValidateBlueprintWorkflowUseCase:
    def execute(self, state: GraphState, approved: bool) -> GraphState:
        if state.presentation is None or state.presentation.blueprint is None:
            raise WorkflowError("BLUEPRINT_NOT_GENERATED", "Generate a blueprint before validating it.")
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.AWAITING_BLUEPRINT_APPROVAL,),
            "approve the blueprint",
        )
        if not approved:
            raise WorkflowError("BLUEPRINT_NOT_APPROVED", "Blueprint was not approved by the human reviewer.")
        if state.presentation.agenda is None or not state.presentation.agenda.is_validated:
            raise WorkflowError("AGENDA_NOT_APPROVED", "Review and approve the proposed agenda before approving the blueprint.")
        if not all(outline.is_validated for outline in state.presentation.blueprint.slides):
            raise WorkflowError("BLUEPRINT_ITEMS_PENDING", "Approve every blueprint item before approving the complete blueprint.")
        state.presentation.blueprint.is_validated = True
        state.presentation.state.blueprint_validated = True
        state.presentation.state.workflow_status = WorkflowStatus.SLIDE_GENERATION
        return state


class GenerateSlidesWorkflowUseCase:
    def execute(self, state: GraphState) -> GraphState:
        if state.presentation is None or not state.presentation.state.blueprint_validated:
            raise WorkflowError("BLUEPRINT_NOT_VALIDATED", "Validate the blueprint before generating slides.")
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.SLIDE_GENERATION,),
            "generate slides",
        )
        clarification = PresentationCompatibilityValidator().clarification_message(state.presentation)
        if clarification:
            state.presentation.state.workflow_status = WorkflowStatus.AWAITING_SCOPE_CLARIFICATION
            raise WorkflowError("PRESENTATION_SCOPE_CLARIFICATION_REQUIRED", clarification)
        presentation = GenerateSlidesUseCase().execute(state.presentation)
        return state.model_copy(update={"presentation": presentation})


class ValidateSlidesWorkflowUseCase:
    def execute(self, state: GraphState, approved: bool) -> GraphState:
        if state.presentation is None or not state.presentation.slides:
            raise WorkflowError("SLIDES_NOT_GENERATED", "Generate slides before validating them.")
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.AWAITING_SLIDE_APPROVAL,),
            "approve slides",
        )
        if not approved:
            raise WorkflowError("SLIDES_NOT_APPROVED", "Slides were not approved by the human reviewer.")
        if not all(slide.is_validated for slide in state.presentation.slides):
            raise WorkflowError("SLIDE_ITEMS_PENDING", "Approve every slide before approving all slides.")
        state.presentation.state.slides_validated = True
        state.presentation.state.workflow_status = WorkflowStatus.AWAITING_FINAL_APPROVAL
        return state


class ReviewBlueprintItemUseCase:
    def execute(self, state: GraphState, index: int, comments: str | None) -> GraphState:
        if state.presentation is None or state.presentation.blueprint is None:
            raise ValueError("Generate a blueprint before reviewing it.")
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.AWAITING_BLUEPRINT_APPROVAL,),
            "review a blueprint item",
        )
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
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.AWAITING_SLIDE_APPROVAL,),
            "review a slide",
        )
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
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.AWAITING_BLUEPRINT_APPROVAL,),
            "reject a blueprint item",
        )
        if not 0 <= index < len(state.presentation.blueprint.slides):
            raise ValueError("Blueprint item index is invalid.")
        item = state.presentation.blueprint.slides[index]
        item.is_validated = False
        item.reviewer_comments = comments.strip() or "Revision requested by reviewer."
        state.presentation.blueprint.is_validated = False
        state.presentation.state.blueprint_validated = False
        state.presentation.state.workflow_status = WorkflowStatus.AWAITING_BLUEPRINT_APPROVAL
        return state


class RejectSlideUseCase:
    def execute(self, state: GraphState, index: int, comments: str) -> GraphState:
        if state.presentation is None or not state.presentation.slides:
            raise ValueError("Generate slides before reviewing them.")
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.AWAITING_SLIDE_APPROVAL,),
            "reject a slide",
        )
        if not 0 <= index < len(state.presentation.slides):
            raise ValueError("Slide index is invalid.")
        slide = state.presentation.slides[index]
        slide.is_validated = False
        slide.reviewer_comments = comments.strip() or "Revision requested by reviewer."
        state.presentation.state.slides_validated = False
        state.presentation.state.presentation_validated = False
        state.presentation.state.workflow_status = WorkflowStatus.AWAITING_SLIDE_APPROVAL
        return state


class RegenerateBlueprintUseCase:
    def execute(self, state: GraphState) -> GraphState:
        if state.presentation is None or state.presentation.blueprint is None:
            raise ValueError("Generate a blueprint before requesting revisions.")
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.AWAITING_AGENDA_APPROVAL, WorkflowStatus.AWAITING_BLUEPRINT_APPROVAL),
            "regenerate the blueprint",
        )
        clarification = PresentationCompatibilityValidator().clarification_message(state.presentation)
        if clarification:
            state.presentation.state.workflow_status = WorkflowStatus.AWAITING_SCOPE_CLARIFICATION
            raise WorkflowError("PRESENTATION_SCOPE_CLARIFICATION_REQUIRED", clarification)
        presentation = BuildBlueprintUseCase().execute(state.presentation)
        presentation.state.blueprint_validated = False
        presentation.state.slides_validated = False
        presentation.state.presentation_validated = False
        return state.model_copy(update={"presentation": presentation})


class RegenerateSlideUseCase:
    def execute(self, state: GraphState, index: int) -> GraphState:
        if state.presentation is None or state.presentation.blueprint is None:
            raise ValueError("Generate a blueprint before regenerating a slide.")
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.AWAITING_SLIDE_APPROVAL,),
            "regenerate a slide",
        )
        if not 0 <= index < len(state.presentation.slides):
            raise ValueError("Slide index is invalid.")
        from app.ai.chains.slide_chain import SlideChain
        from app.ai.mappers.slide_mapper import SlideMapper
        from app.application.validators.evidence_provenance_validator import EvidenceProvenanceValidator

        outline = state.presentation.blueprint.slides[index]
        evidence_error = ProductionEvidenceGate.generation_error(
            state.presentation,
            f"{state.presentation.context.topic} {outline.title} {outline.objective} {outline.key_message}",
        )
        if evidence_error:
            raise WorkflowError("INSUFFICIENT_EVIDENCE", evidence_error)

        replacement = SlideMapper().to_domain(
            SlideChain().invoke(state.presentation, outline)
        )
        EvidenceProvenanceValidator().validate_slide(replacement, state.presentation.resources)
        replacement.reviewer_comments = state.presentation.slides[index].reviewer_comments
        state.presentation.slides[index] = replacement
        state.presentation.state.slides_validated = False
        state.presentation.state.presentation_validated = False
        state.presentation.state.workflow_status = WorkflowStatus.AWAITING_SLIDE_APPROVAL
        return state


class ValidateFinalPresentationWorkflowUseCase:
    def execute(self, state: GraphState, approved: bool) -> GraphState:
        if state.presentation is None or not state.presentation.state.slides_validated:
            raise WorkflowError("SLIDES_NOT_VALIDATED", "Validate slides before approving the final presentation.")
        WorkflowPolicy.require_status(
            state.presentation.state.workflow_status,
            (WorkflowStatus.AWAITING_FINAL_APPROVAL,),
            "approve the final presentation",
        )
        if not approved:
            raise WorkflowError("FINAL_APPROVAL_REQUIRED", "Final presentation was not approved by the human reviewer.")
        state.presentation.state.presentation_validated = True
        state.presentation.state.workflow_status = WorkflowStatus.READY_FOR_EXPORT
        return state
