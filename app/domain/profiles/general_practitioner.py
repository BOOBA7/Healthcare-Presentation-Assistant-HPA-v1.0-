from app.domain.enums.audience_type import AudienceType
from app.domain.value_objects.audience_profile import AudienceProfile


def build_general_practitioner_profile() -> AudienceProfile:

    return AudienceProfile(
        audience_type=AudienceType.GENERAL_PRACTITIONER,
        knowledge_level="intermediate",
        explanation_level="detailed",
        statistics_level="basic",
        terminology_level="intermediate",
        preferred_visuals=[
            "clinical_algorithm",
            "patient_case",
            "treatment_flowchart",
            "simple_bar_chart",
        ],
        learning_focus="clinical_practice",
        interaction_style="practical",
        presenter_expectations=[
            "clear key messages",
            "clinical applicability",
            "simple explanations",
            "guideline recommendations",
        ],
    )
