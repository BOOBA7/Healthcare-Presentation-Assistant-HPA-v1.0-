from app.domain.enums.audience_type import AudienceType
from app.domain.value_objects.audience_profile import AudienceProfile


def build_specialist_profile() -> AudienceProfile:

    return AudienceProfile(
        audience_type=AudienceType.SPECIALIST,
        knowledge_level="expert",
        explanation_level="minimal",
        statistics_level="advanced",
        terminology_level="expert",
        preferred_visuals=[
            "forest_plot",
            "kaplan_meier_curve",
            "clinical_trial_schema",
            "meta_analysis",
        ],
        learning_focus="clinical_evidence",
        interaction_style="scientific_discussion",
        presenter_expectations=[
            "high scientific accuracy",
            "latest guidelines",
            "critical analysis",
            "clinical relevance",
        ],
    )
