from enum import Enum


class PresentationTheme(str, Enum):
    """Professional visual themes available for exported PowerPoint decks."""

    CLINICAL = "clinical"
    ACADEMIC = "academic"
    EXECUTIVE = "executive"
    MIDNIGHT = "midnight"
