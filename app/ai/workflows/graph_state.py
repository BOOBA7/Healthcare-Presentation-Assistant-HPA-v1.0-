from typing import Any, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.conversation_context import ConversationContext
from app.domain.models.presentation import Presentation
from app.domain.models.user_profile import UserProfile
from app.domain.value_objects.presentation_context import PresentationContext


class GraphState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    conversation_context: ConversationContext = Field(default_factory=ConversationContext)
    presentation_context: PresentationContext | None = None
    presentation: Presentation | None = None
    user_profile: UserProfile = Field(default_factory=UserProfile)
    last_tool: str | None = None
    tool_output: Any | None = None
    error: str | None = None
