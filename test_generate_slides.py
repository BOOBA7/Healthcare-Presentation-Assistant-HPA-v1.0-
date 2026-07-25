from pathlib import Path

from app.application.use_cases.build_blueprint import BuildBlueprintUseCase
from app.application.use_cases.create_presentation import (
    CreatePresentationUseCase,
)
from app.application.use_cases.generate_slides import (
    GenerateSlidesUseCase,
)
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.models.resource import Resource
from app.domain.value_objects.presentation_context import (
    PresentationContext,
)

context = PresentationContext(
    topic="Heart Failure Management",
    audience=AudienceType.SPECIALIST,
    presentation_type=PresentationType.SYMPOSIUM,
    language=Language.ENGLISH,
    duration_minutes=30,
    objective="Update cardiologists on the latest ESC heart failure guidelines.",
)

presentation = CreatePresentationUseCase().execute(
    title="Heart Failure Management",
    context=context,
)

presentation.resources.append(
    Resource(
        id="1",
        filename="ESC_Heart_Failure_Guidelines_2023.pdf",
        file_type="pdf",
        path=str(Path("documents/ESC_Heart_Failure_Guidelines_2023.pdf")),
        title="2023 ESC Heart Failure Guidelines",
    )
)

presentation = BuildBlueprintUseCase().execute(
    presentation,
)

presentation = GenerateSlidesUseCase().execute(
    presentation,
)

print("\n========== GENERATED SLIDES ==========\n")

for slide in presentation.slides:
    print(f"Slide {slide.slide_number}")

    print(f"Title : {slide.title}")

    print(f"Objective : {slide.objective}")

    print("\nKey Messages")

    for message in slide.key_messages:
        print(f" - {message}")

    print("\nContent")

    print(slide.content)

    print("\nSpeaker Notes")

    print(slide.speaker_notes)

    print("\nReferences")

    for reference in slide.references:
        print(f" - {reference}")

    print("\nVisual Recommendations")

    for visual in slide.visual_recommendations:
        print(f" - {visual}")

    print("\n" + "=" * 80 + "\n")
