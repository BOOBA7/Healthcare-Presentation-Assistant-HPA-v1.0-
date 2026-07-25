from enum import Enum


class Language(str, Enum):
    """
    Supported presentation languages.
    """

    ENGLISH = "English"

    FRENCH = "French"

    ARABIC = "Arabic"

    SPANISH = "Spanish"

    GERMAN = "German"

    ITALIAN = "Italian"
