"""Explicit boundary between planning chat and evidence-bound production."""

from enum import Enum


class ConversationMode(str, Enum):
    GENERAL = "general"
    PRODUCTION = "production"
