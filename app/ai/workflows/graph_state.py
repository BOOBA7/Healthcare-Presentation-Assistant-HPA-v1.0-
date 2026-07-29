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
from app.domain.models.resource_chunk import ResourceChunk
from app.domain.models.resource_analysis import ResourceAnalysis
from app.domain.value_objects.presentation_context import PresentationContext
from app.domain.enums.conversation_mode import ConversationMode


class GraphState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    # Presentation-assistant transcript. It never contains resource-only
    # overview or PDF-discussion turns.
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    # Compact, non-authoritative continuity memory used when old model messages
    # are removed from the active context window. The full transcript remains
    # in ``conversation_history`` for the user and audit trail.
    conversation_memory_summary: str = ""
    # Exploration transcript for the Project PDF library. It is deliberately
    # independent from the agent's workflow conversation.
    resource_conversation_history: list[ConversationTurn] = Field(default_factory=list)
    # Optimistic-lock revision supplied by the SQLite repository.  It is not a
    # workflow approval and must change on every durable Project write.
    project_revision: int = Field(default=0, ge=0)
    conversation_mode: ConversationMode = ConversationMode.GENERAL
    # The project owns uploaded documents. A presentation only keeps an
    # explicit selection from this library for controlled production.
    resource_library: list[Resource] = Field(default_factory=list)
    # Retrieval cache loaded from the normalized SQLite chunk table. It is
    # deliberately excluded from the durable workflow JSON snapshot.
    resource_chunks: list[ResourceChunk] = Field(default_factory=list)
    resource_analysis: ResourceAnalysis | None = None
    conversation_context: ConversationContext = Field(default_factory=ConversationContext)
    presentation_context: PresentationContext | None = None
    presentation: Presentation | None = None
    user_profile: UserProfile = Field(default_factory=UserProfile)
    execution: ExecutionContext = Field(default_factory=ExecutionContext)
