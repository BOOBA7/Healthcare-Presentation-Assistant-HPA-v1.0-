from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Role(str, Enum):
    """
    Represents the role of a message sender.
    """

    USER = "user"

    ASSISTANT = "assistant"

    SYSTEM = "system"


class ChatMessage(BaseModel):
    """
    Represents one message exchanged during
    a conversation with the Healthcare Presentation Assistant.
    """

    role: Role

    content: str

    timestamp: datetime = Field(
        default_factory=datetime.now,
    )
