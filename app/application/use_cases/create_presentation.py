from datetime import datetime
from uuid import uuid4

from app.domain.models.presentation import Presentation
from app.domain.models.presentation_state import PresentationState
from app.domain.profiles.profile_registry import ProfileRegistry
from app.domain.value_objects.presentation_context import (
    PresentationContext,
)


class CreatePresentationUseCase:
    """
    Creates a new healthcare presentation.
    """

    def execute(
        self,
        title: str,
        context: PresentationContext,
    ) -> Presentation:
        """
        Create and initialize a Presentation domain object.

        Parameters
        ----------
        title:
            Presentation title.

        context:
            Presentation context collected from the conversation.

        Returns
        -------
        Presentation
        """

        audience_profile = ProfileRegistry().get_profile(
            context.audience,
        )

        presentation_state = PresentationState(
            context=context,
            audience_profile=audience_profile,
        )

        return Presentation(
            id=str(uuid4()),
            title=title,
            context=context,
            state=presentation_state,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
