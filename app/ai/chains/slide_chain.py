from app.ai.llm.llm import get_llm
from app.ai.prompt_builders.slide_prompt_builder import (
    SlidePromptBuilder,
)
from app.ai.schemas.slide_schema import SlideSchema
from app.domain.models.presentation import Presentation
from app.domain.models.slide_outline import SlideOutline
from app.domain.models.resource import Resource
from app.domain.models.resource_chunk import ResourceChunk
from app.application.services.observability import observe_llm_call


class SlideChain:
    """
    Generates a structured presentation slide
    using the configured LLM.
    """

    def __init__(self) -> None:
        self.llm = get_llm()
        self.prompt_builder = SlidePromptBuilder()

    def invoke(
        self,
        presentation: Presentation,
        outline: SlideOutline,
        resources: list[Resource] | None = None,
        chunks: list[ResourceChunk] | None = None,
        reviewer_comments: str | None = None,
    ) -> SlideSchema:
        """
        Generate a single slide from the blueprint.
        """

        prompt = self.prompt_builder.build(
            presentation=presentation,
            outline=outline,
            resources=resources,
            chunks=chunks,
            reviewer_comments=reviewer_comments,
        )

        structured_llm = self.llm.with_structured_output(
            SlideSchema,
        )

        result = observe_llm_call("slide_generation", prompt, lambda: structured_llm.invoke(prompt))

        return result
