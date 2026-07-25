import logging
from collections.abc import Sequence

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from app.ai.harness.healthcare_harness import HEALTHCARE_HARNESS
from app.ai.llm.llm import get_llm
from app.ai.prompts.loop_engineering import LOOP_ENGINEERING
from app.ai.prompts.system_prompt import SYSTEM_PROMPT
from app.ai.workflows.tools import TOOLS

logger = logging.getLogger(__name__)


class AgentBuilder:
    """
    Builds the LangChain cognitive Runnable used by the
    Healthcare Presentation Assistant.
    """

    def __init__(self, tools: Sequence[BaseTool] | None = None) -> None:
        self.chat_model = get_llm()
        self.tools = list(tools or TOOLS)


    def build(self) -> Runnable:
        logger.info("Building cognitive agent...")

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self._build_system_prompt()),
                ("system", "{state_summary}"),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        runnable = prompt | self.chat_model.bind_tools(self.tools)

        logger.info("Cognitive agent successfully built.")
        return runnable

    def _build_system_prompt(self) -> str:
        return "\n\n".join(
            [
                SYSTEM_PROMPT.strip(),
                HEALTHCARE_HARNESS.strip(),
                LOOP_ENGINEERING.strip(),
            ]
        )
