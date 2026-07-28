from typing import Any, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.conversation_context import ConversationContext
from app.domain.models.presentation import Presentation
from app.domain.models.user_profile import UserProfile
from app.domain.models.execution_context import ExecutionContext
from app.domain.models.conversation_turn import ConversationTurn
from app.domain.models.resource import Resource
from app.domain.models.resource_analysis import ResourceAnalysis
from app.domain.value_objects.presentation_context import PresentationContext
from app.domain.enums.conversation_mode import ConversationMode


class GraphState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    conversation_mode: ConversationMode = ConversationMode.GENERAL
    # The project owns uploaded documents. A presentation only keeps an
    # explicit selection from this library for controlled production.
    resource_library: list[Resource] = Field(default_factory=list)
    resource_analysis: ResourceAnalysis | None = None
    conversation_context: ConversationContext = Field(default_factory=ConversationContext)
    presentation_context: PresentationContext | None = None
    presentation: Presentation | None = None
    user_profile: UserProfile = Field(default_factory=UserProfile)
    execution: ExecutionContext = Field(default_factory=ExecutionContext)
