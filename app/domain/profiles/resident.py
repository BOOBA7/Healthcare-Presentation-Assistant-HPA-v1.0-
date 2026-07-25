from app.domain.enums.audience_type import AudienceType
from app.domain.value_objects.audience_profile import AudienceProfile


def build_resident_profile() -> AudienceProfile:

    return AudienceProfile(
        audience_type=AudienceType.RESIDENT,
        knowledge_level="advanced",
        explanation_level="detailed",
        statistics_level="intermediate",
        terminology_level="advanced",
        preferred_visuals=[
            "pathophysiology_diagram",
            "clinical_algorithm",
            "trial_schema",
            "decision_tree",
        ],
        learning_focus="clinical_reasoning",
        interaction_style="educational",
        presenter_expectations=[
            "step-by-step explanations",
            "evidence-based medicine",
            "guideline interpretation",
            "clinical cases",
        ],
    )
