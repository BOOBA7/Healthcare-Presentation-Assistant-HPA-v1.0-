from enum import Enum


class AudienceType(str, Enum):
    GENERAL_PRACTITIONER = "general_practitioner"
    RESIDENT = "Resident"
    MEDICAL_STUDENT = "Medical Student"
    SPECIALIST = "Specialist"
    MEDICAL_REPRESENTATIVE = "Medical Representative"
    MEDICAL_SCIENCE_LIAISON = "Medical Science Liaison"
    PHARMACIST = "Pharmacist"
    MIXED_AUDIENCE = "Mixed Audience"
