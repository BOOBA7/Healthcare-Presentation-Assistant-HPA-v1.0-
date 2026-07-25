from enum import Enum


class PresentationType(str, Enum):
    """
    Defines the different types of healthcare presentations.
    """

    LECTURE = "Lecture"
    SYMPOSIUM = "Symposium"
    ROUND_TABLE = "Round Table"
    WORKSHOP = "Workshop"
    JOURNAL_CLUB = "Journal Club"
    ADVISORY_BOARD = "Advisory Board"
    WEBINAR = "Webinar"
    TRAINING = "Training"
    CONGRESS = "Congress"
    PRODUCT_LAUNCH = "Product Launch"
