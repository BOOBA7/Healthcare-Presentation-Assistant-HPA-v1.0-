from app.ai.agents.agent_builder import AgentBuilder
from app.ai.workflows.graph_state import GraphState
from app.ai.workflows.presentation_graph import PresentationGraph
from app.ai.workflows.tools import COGNITIVE_TOOLS


class ConversationService:
    """
    Singleton service responsible for managing
    conversations with the Healthcare Presentation Assistant.

    Responsibilities
    ----------------
    - Build the LangChain agent once.
    - Compile the LangGraph workflow once.
    - Execute conversations.
    - Reuse the same cognitive agent during the
      whole application lifetime.
    """

    def __init__(self) -> None:

        self._agent = AgentBuilder(tools=COGNITIVE_TOOLS).build()

        self._workflow = PresentationGraph(
            agent=self._agent,
            tools=COGNITIVE_TOOLS,
        ).compile()

    @property
    def agent(self):
        """
        Return the LangChain Runnable.
        """

        return self._agent

    @property
    def workflow(self):
        """
        Return the compiled LangGraph workflow.
        """

        return self._workflow

    def invoke(
        self,
        state: GraphState,
        thread_id: str,
    ) -> GraphState:
        """
        Execute one workflow iteration.

        Parameters
        ----------
        state:
            Current workflow state.

        thread_id:
            Persistent LangGraph thread identifier.

        Returns
        -------
        GraphState
            Updated workflow state.
        """

        return self._workflow.invoke(
            state,
            config={
                "configurable": {
                    "thread_id": thread_id,
                }
            },
        )
