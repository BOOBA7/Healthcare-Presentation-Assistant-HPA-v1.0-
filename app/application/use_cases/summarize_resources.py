"""Generate a bounded, source-only overview of uploaded PDF resources."""

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.llm.llm import get_llm
from app.domain.models.resource_analysis import ResourceAnalysis
from app.domain.models.resource import Resource
from app.domain.models.resource_chunk import ResourceChunk
from app.ai.prompt_builders.evidence_context_builder import EvidenceContextBuilder
from app.application.services.observability import observe_llm_call
from app.application.services.patient_case_privacy import PatientCasePrivacyGuard
from app.domain.enums.evidence_context_mode import EvidenceContextMode
from app.application.validators.response_citation_validator import ResponseCitationValidator


class SummarizeResourcesUseCase:
    """Create a discussion starter without creating clinical slide content."""

    def execute(
        self,
        resources: list[Resource],
        language: str = "en",
        chunks: list[ResourceChunk] | None = None,
        evidence_context_mode: EvidenceContextMode = EvidenceContextMode.BM25,
        patient_case_mode: bool = False,
    ) -> ResourceAnalysis:
        if not resources:
            raise ValueError("Upload at least one PDF before requesting a resource overview.")

        if patient_case_mode:
            for resource in resources:
                PatientCasePrivacyGuard().ensure_resource_safe(resource)
        context = EvidenceContextBuilder().for_overview(resources, chunks, evidence_context_mode)
        prompt = [
                SystemMessage(
                    content=(
                        "You summarize only the PDF passages supplied in the user message. "
                        "Do not use external medical knowledge, fill gaps, give clinical advice, or invent citations. "
                        "If the sources are insufficient or inconsistent, say so plainly. "
                        "Write a concise discussion starter with: overall idea, key themes, points of agreement or tension, "
                        "and limitations. Cite every factual claim using exactly "
                        "[[cite: resource_id | p. page | exact verbatim evidence excerpt]]. "
                        f"Respond in the requested presentation language: {language}."
                    )
                ),
                HumanMessage(content=f"USER-UPLOADED PDF PASSAGES:\n{context}"),
            ]
        response = observe_llm_call("resource_overview", prompt, lambda: get_llm().invoke(prompt))
        summary = self._message_text(response).strip()
        if not summary:
            raise ValueError("The model returned an empty resource overview. Please retry.")
        ResponseCitationValidator().validate(summary, resources)
        analysis = ResourceAnalysis(
            summary=summary,
            resource_ids=[resource.id for resource in resources],
        )
        return analysis

    def build_context(
        self,
        resources: list[Resource],
        chunks: list[ResourceChunk] | None = None,
        evidence_context_mode: EvidenceContextMode = EvidenceContextMode.BM25,
    ) -> str:
        context = EvidenceContextBuilder().for_overview(resources, chunks, evidence_context_mode)
        if context.startswith("No relevant"):
            raise ValueError("No readable text is available in the uploaded PDFs.")
        return context

    @staticmethod
    def _message_text(response: object) -> str:
        content = getattr(response, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            )
        return str(content)
