from typing import List

from app.domain.models.resource import Resource


class ResourceValidator:
    """
    Validates uploaded scientific resources before
    the presentation generation workflow continues.
    """

    def validate(self, resources: List[Resource]) -> tuple[bool, List[str]]:
        """
        Validate a list of uploaded resources.

        Args:
            resources: List of uploaded resources.

        Returns:
            A tuple containing:
            - True/False indicating whether validation succeeded.
            - A list of validation messages.
        """

        messages: List[str] = []

        if not resources:
            messages.append("At least one resource must be provided.")
            return False, messages

        for resource in resources:
            if not resource.filename.strip():
                messages.append(f"Resource '{resource.id}' has no filename.")

            if not resource.file_type.strip():
                messages.append(f"Resource '{resource.filename}' has no file type.")

            if resource.extracted_text is None:
                messages.append(
                    f"Resource '{resource.filename}' has not been parsed yet."
                )

            elif not resource.extracted_text.strip():
                messages.append(
                    f"Resource '{resource.filename}' contains no extracted text."
                )

            if not resource.is_validated:
                messages.append(
                    f"Resource '{resource.filename}' has not been validated by the user."
                )

        is_valid = len(messages) == 0

        return is_valid, messages
