"""Answer questions about the project PDF library without entering production."""

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.llm.llm import get_llm
from app.application.use_cases.summarize_resources import SummarizeResourcesUseCase
from app.domain.models.resource import Resource


class DiscussResourcesUseCase:
    def execute(self, resources: list[Resource], question: str, language: str = "en") -> str:
        question = question.strip()
        if not question:
            raise ValueError("Enter a question about the uploaded resources.")
        context = SummarizeResourcesUseCase().build_context(resources)
        response = get_llm().invoke([
            SystemMessage(content=(
                "Answer only from the supplied user-uploaded PDF passages. Do not use external knowledge, "
                "give clinical advice, invent facts, or invent citations. If the answer is absent, ambiguous, "
                "or inconsistent in the sources, say that you cannot answer from these resources and ask what "
                "additional source or clarification is needed. Cite every factual claim as [resource_id, p. page]. "
                f"Reply in {language}."
            )),
            HumanMessage(content=f"QUESTION: {question}\n\nUSER-UPLOADED PDF PASSAGES:\n{context}"),
        ])
        answer = SummarizeResourcesUseCase._message_text(response).strip()
        if not answer:
            raise ValueError("The model returned an empty resource discussion response. Please retry.")
        return answer
