"""Answer questions about the project PDF library without entering production."""

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.llm.llm import get_llm
from app.application.use_cases.summarize_resources import SummarizeResourcesUseCase
from app.ai.prompt_builders.evidence_context_builder import EvidenceContextBuilder
from app.domain.models.resource import Resource
from app.domain.models.resource_chunk import ResourceChunk
from app.application.services.observability import observe_llm_call
from app.application.services.patient_case_privacy import PatientCasePrivacyGuard
from app.domain.enums.evidence_context_mode import EvidenceContextMode


class DiscussResourcesUseCase:
    def execute(
        self,
        resources: list[Resource],
        question: str,
        language: str = "en",
        chunks: list[ResourceChunk] | None = None,
        evidence_context_mode: EvidenceContextMode = EvidenceContextMode.BM25,
        patient_case_mode: bool = False,
    ) -> str:
        question = question.strip()
        if not question:
            raise ValueError("Enter a question about the uploaded resources.")
        if patient_case_mode:
            guard = PatientCasePrivacyGuard()
            guard.ensure_text_safe(question)
            for resource in resources:
                guard.ensure_resource_safe(resource)
        context = EvidenceContextBuilder().for_resources(resources, question, chunks, evidence_context_mode)
        if context.startswith("No relevant"):
            raise ValueError("The uploaded PDFs do not contain relevant readable passages for this question.")
        prompt = [
            SystemMessage(content=(
                "Answer only from the supplied user-uploaded PDF passages. Do not use external knowledge, "
                "give clinical advice, invent facts, or invent citations. If the answer is absent, ambiguous, "
                "or inconsistent in the sources, say that you cannot answer from these resources and ask what "
                "additional source or clarification is needed. Cite every factual claim as [resource_id, p. page]. "
                f"Reply in {language}."
            )),
            HumanMessage(content=f"QUESTION: {question}\n\nUSER-UPLOADED PDF PASSAGES:\n{context}"),
        ]
        response = observe_llm_call("resource_discussion", prompt, lambda: get_llm().invoke(prompt))
        answer = SummarizeResourcesUseCase._message_text(response).strip()
        if not answer:
            raise ValueError("The model returned an empty resource discussion response. Please retry.")
        return answer
