from app.application.use_cases.build_blueprint import (
    BuildBlueprintUseCase,
)
from app.application.use_cases.generate_slides import (
    GenerateSlidesUseCase,
)
from app.domain.models.presentation import Presentation


class ChatController:
    """
    Orchestrates user interactions with the
    Healthcare Presentation Assistant.

    This controller delegates business logic
    to the appropriate application use cases.
    """

    def __init__(self) -> None:

        self.blueprint_use_case = BuildBlueprintUseCase()

        self.generate_slides_use_case = GenerateSlidesUseCase()

    def generate_blueprint(
        self,
        presentation: Presentation,
    ) -> Presentation:
        """
        Generate the presentation blueprint.
        """

        return self.blueprint_use_case.execute(
            presentation,
        )

    def generate_slides(
        self,
        presentation: Presentation,
    ) -> Presentation:
        """
        Generate all presentation slides.
        """

        return self.generate_slides_use_case.execute(
            presentation,
        )

    def process_command(
        self,
        command: str,
        presentation: Presentation,
    ) -> Presentation:
        """
        Process a simple chat command.

        This implementation is intentionally
        lightweight. It will later be replaced
        by an LLM-powered intent router.
        """

        command = command.lower().strip()

        if command in {
            "blueprint",
            "generate blueprint",
        }:
            return self.generate_blueprint(
                presentation,
            )

        if command in {
            "slides",
            "generate slides",
        }:
            return self.generate_slides(
                presentation,
            )

        raise ValueError(f"Unknown command: {command}")
