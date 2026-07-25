from typing import List

from app.domain.enums.audience_type import AudienceType


class AudienceValidator:
    """
    Validates the selected audience before the presentation
    generation workflow continues.
    """

    def validate(self, audience: AudienceType) -> tuple[bool, List[str]]:
        """
        Validate the selected audience.

        Args:
            audience: The selected audience type.

        Returns:
            A tuple containing:
            - True if validation succeeds.
            - A list of validation messages.
        """

        messages: List[str] = []

        if audience is None:
            messages.append("An audience must be selected.")
            return False, messages

        if not isinstance(audience, AudienceType):
            messages.append("Invalid audience type.")
            return False, messages

        return True, messages
