from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    """Stable UI-facing transcript entry, independent from provider message formats."""

    role: Literal["user", "assistant"]
    text: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=datetime.now)
