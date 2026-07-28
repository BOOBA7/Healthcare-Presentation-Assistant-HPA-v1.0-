"""Checks whether the declared delivery context needs human clarification."""

from app.domain.enums.audience_type import AudienceType
from app.domain.models.presentation import Presentation
from app.domain.models.resource import Resource


class PresentationCompatibilityValidator:
    """Conservative context check; it asks, never guesses a user's authority."""

    human_clinical_audiences = {
        AudienceType.GENERAL_PRACTITIONER,
        AudienceType.RESIDENT,
        AudienceType.MEDICAL_STUDENT,
        AudienceType.SPECIALIST,
        AudienceType.PHARMACIST,
        AudienceType.MEDICAL_REPRESENTATIVE,
        AudienceType.MEDICAL_SCIENCE_LIAISON,
        AudienceType.MIXED_AUDIENCE,
    }

    def clarification_message(
        self, presentation: Presentation, resources: list[Resource] | None = None
    ) -> str | None:
        """Return the one clarification required before scientific production."""
        if presentation.professional_scope and presentation.professional_scope.strip():
            return None
        if (
            presentation.owner_profile.professional_role == "veterinarian"
            and presentation.context.audience in self.human_clinical_audiences
        ):
            return (
                "Your professional profile is veterinarian, while this presentation targets a human "
                "healthcare audience. Before generating the blueprint, explain your role and the "
                "legitimate scope of this presentation (for example, medical representative with "
                "veterinary training)."
            )
        if (
            presentation.context.audience in self.human_clinical_audiences
            and self._has_veterinary_resource_signal(resources if resources is not None else presentation.resources)
        ):
            return (
                "At least one validated resource appears to concern veterinary or animal health, while "
                "the intended audience is human healthcare. Confirm the intended scope or provide a "
                "human-health resource before generating the blueprint."
            )
        return None

    @staticmethod
    def _has_veterinary_resource_signal(resources: list[Resource]) -> bool:
        signals = ("veterinary", "veterinarian", "canine", "feline", "equine", "animal health")
        for resource in resources:
            if not resource.is_validated:
                continue
            metadata = " ".join(filter(None, [resource.filename, resource.title, resource.source])).casefold()
            if any(signal in metadata for signal in signals):
                return True
        return False
