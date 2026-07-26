from typing import Literal

from pydantic import BaseModel


ProfessionalRole = Literal[
    "professor_medicine",
    "assistant_professor",
    "veterinarian",
    "biologist",
    "specialist_physician",
    "resident_physician",
]
PreferredLanguage = Literal["en", "fr", "ar"]


class UserProfile(BaseModel):
    """Professional context used to adapt the assistant's communication style."""

    professional_role: ProfessionalRole = "resident_physician"
    preferred_language: PreferredLanguage = "en"
