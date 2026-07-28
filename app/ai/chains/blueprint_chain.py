from app.ai.llm.llm import get_llm
from app.ai.prompt_builders.blueprint_prompt_builder import BlueprintPromptBuilder
from app.ai.schemas.blueprint_schema import BlueprintSchema
from app.domain.models.presentation import Presentation
from app.domain.models.resource import Resource
from app.application.services.observability import observe_llm_call


class BlueprintChain:
    """
    Generates a structured presentation blueprint
    using the configured LLM.
    """

    def __init__(self) -> None:
        self.llm = get_llm()
        self.prompt_builder = BlueprintPromptBuilder()

    def invoke(
        self,
        presentation: Presentation,
        resources: list[Resource] | None = None,
    ) -> BlueprintSchema:
        """
        Generate a blueprint from the presentation context.
        """

        prompt = self.prompt_builder.build(presentation, resources)

        structured_llm = self.llm.with_structured_output(BlueprintSchema)

        result = observe_llm_call("blueprint_generation", prompt, lambda: structured_llm.invoke(prompt))

        return result
