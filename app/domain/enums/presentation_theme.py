from enum import Enum


class PresentationTheme(str, Enum):
    """Professional visual themes available for exported PowerPoint decks."""

    CLINICAL = "clinical"
    ACADEMIC = "academic"
    EXECUTIVE = "executive"
    MIDNIGHT = "midnight"


class PresentationColour(str, Enum):
    """Finite colour choices offered during explicit style selection."""

    THEME = "theme"
    TEAL = "teal"
    BLUE = "blue"
    WARM = "warm"
