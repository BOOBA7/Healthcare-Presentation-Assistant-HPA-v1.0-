from app.ai.workflows.graph_state import GraphState


class CollectPresentationContextTool:
    """
    Merge the structured information extracted by the agent
    into the ConversationContext.

    This tool never performs NLP parsing.
    It only updates the conversation state.
    """

    def __call__(self, state: GraphState) -> GraphState:
        """
        Update the ConversationContext with the data
        extracted by the cognitive agent.
        """
        extracted = state.tool_output

        if extracted is None:
            return state

        context = state.conversation_context

        for field, value in extracted.model_dump(exclude_none=True).items():
            setattr(context, field, value)

        return state
