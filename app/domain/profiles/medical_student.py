from app.domain.enums.audience_type import AudienceType
from app.domain.value_objects.audience_profile import AudienceProfile


def build_medical_student_profile() -> AudienceProfile:

    return AudienceProfile(
        audience_type=AudienceType.MEDICAL_STUDENT,
        knowledge_level="beginner",
        explanation_level="very_detailed",
        statistics_level="basic",
        terminology_level="basic",
        preferred_visuals=[
            "anatomy_diagram",
            "physiology_schema",
            "illustration",
            "flowchart",
        ],
        learning_focus="foundational_learning",
        interaction_style="teaching",
        presenter_expectations=[
            "simple language",
            "definitions",
            "step-by-step concepts",
            "illustrated explanations",
        ],
    )
