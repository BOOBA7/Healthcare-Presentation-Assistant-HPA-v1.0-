from uuid import uuid4

from app.application.use_cases.build_blueprint import BuildBlueprintUseCase

from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.enums.presentation_status import PresentationStatus
from app.domain.enums.workflow_step import WorkflowStep

from app.domain.models.presentation import Presentation
from app.domain.models.presentation_state import PresentationState
from app.domain.models.resource import Resource

from app.domain.value_objects.presentation_context import PresentationContext
from app.domain.value_objects.audience_profile import AudienceProfile


# ==========================
# Presentation Context
# ==========================

context = PresentationContext(
    topic="Heart Failure",
    audience=AudienceType.SPECIALIST,
    presentation_type=PresentationType.SYMPOSIUM,
    language=Language.ENGLISH,
    duration_minutes=30,
    objective="Present the latest evidence-based recommendations for heart failure management.",
)


# ==========================
# Audience Profile
# ==========================

audience_profile = AudienceProfile(
    audience_type=AudienceType.SPECIALIST,
    knowledge_level="Expert",
    explanation_level="Advanced scientific",
    statistics_level="Clinical trial level",
    terminology_level="Medical terminology",
    preferred_visuals=[
        "Clinical algorithms",
        "Guideline tables",
        "Clinical trial graphs",
    ],
    learning_focus="Clinical decision making",
    interaction_style="Scientific conference",
    presenter_expectations=[
        "Evidence-based content",
        "Recent guidelines",
    ],
)


# ==========================
# Presentation
# ==========================

presentation = Presentation(
    id=str(uuid4()),
    title="Heart Failure Management: Current Evidence and Guidelines",
    context=context,
    state=PresentationState(
        context=context,
        audience_profile=audience_profile,
        current_step=WorkflowStep.BLUEPRINT_GENERATION,
    ),
    status=PresentationStatus.DRAFT,
    resources=[
        Resource(
            id=str(uuid4()),
            filename="ESC_Heart_Failure_Guidelines.pdf",
            title="ESC Guidelines for Heart Failure Management",
            file_type="pdf",
        )
    ],
)


# ==========================
# Execute Blueprint Generation
# ==========================

use_case = BuildBlueprintUseCase()

result = use_case.execute(presentation)


# ==========================
# Display Result
# ==========================

print("\n========== BLUEPRINT ==========\n")

if result.blueprint:
    print(result.blueprint.model_dump_json(indent=2))
else:
    print("No blueprint generated")
