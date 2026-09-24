from app.ai.llm.llm import get_llm
from app.ai.prompt_builders.agenda_prompt_builder import AgendaPromptBuilder
from app.ai.schemas.agenda_schema import AgendaSchema
from app.application.services.observability import observe_llm_call
from app.application.services.presentation_context_policy import PresentationContextPolicy
from app.application.services.prototype_policy import PrototypePolicy
from app.application.services.source_date_policy import SourceDatePolicy
from app.domain.models.presentation import Presentation
from app.domain.models.resource import Resource
from app.domain.models.resource_chunk import ResourceChunk


class AgendaChain:
    def __init__(self) -> None:
        self.llm = get_llm()
        self.prompt_builder = AgendaPromptBuilder()

    def invoke(
        self,
        presentation: Presentation,
        resources: list[Resource] | None = None,
        chunks: list[ResourceChunk] | None = None,
    ) -> AgendaSchema:
        PrototypePolicy.presentation(presentation)
        PresentationContextPolicy.require(presentation)
        SourceDatePolicy.require_all(resources or presentation.resources)
        prompt = self.prompt_builder.build(presentation, resources, chunks)
        structured_llm = self.llm.with_structured_output(AgendaSchema)
        return observe_llm_call("agenda_generation", prompt, lambda: structured_llm.invoke(prompt))
