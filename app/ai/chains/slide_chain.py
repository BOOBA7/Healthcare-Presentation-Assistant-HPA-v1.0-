from app.ai.llm.llm import get_llm
from app.ai.prompt_builders.slide_prompt_builder import (
    SlidePromptBuilder,
)
from app.ai.schemas.slide_schema import SlideSchema
from app.domain.models.presentation import Presentation
from app.domain.models.slide_outline import SlideOutline


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
    ) -> SlideSchema:
        """
        Generate a single slide from the blueprint.
        """

        prompt = self.prompt_builder.build(
            presentation=presentation,
            outline=outline,
        )

        structured_llm = self.llm.with_structured_output(
            SlideSchema,
        )

        result = structured_llm.invoke(prompt)

        return result
