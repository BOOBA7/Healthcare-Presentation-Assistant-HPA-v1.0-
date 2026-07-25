from app.domain.enums.audience_type import AudienceType
from app.domain.value_objects.audience_profile import AudienceProfile

from app.domain.profiles.specialist import build_specialist_profile
from app.domain.profiles.resident import build_resident_profile
from app.domain.profiles.general_practitioner import (
    build_general_practitioner_profile,
)
from app.domain.profiles.medical_student import (
    build_medical_student_profile,
)


class ProfileRegistry:
    """
    Responsible for retrieving the correct AudienceProfile
    based on the selected AudienceType.
    """

    def __init__(self):

        self._profiles = {
            AudienceType.SPECIALIST: build_specialist_profile,
            AudienceType.RESIDENT: build_resident_profile,
            AudienceType.GENERAL_PRACTITIONER: build_general_practitioner_profile,
            AudienceType.MEDICAL_STUDENT: build_medical_student_profile,
        }

    def get_profile(self, audience: AudienceType) -> AudienceProfile:

        builder = self._profiles.get(audience)

        if builder is None:
            raise ValueError(f"No profile registered for {audience}")

        return builder()
