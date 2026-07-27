"""Generate a bounded, source-only overview of uploaded PDF resources."""

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.llm.llm import get_llm
from app.domain.models.resource_analysis import ResourceAnalysis
from app.domain.models.resource import Resource


class SummarizeResourcesUseCase:
    """Create a discussion starter without creating clinical slide content."""

    max_characters = 18_000
    max_characters_per_resource = 6_000

    def execute(self, resources: list[Resource], language: str = "en") -> ResourceAnalysis:
        if not resources:
            raise ValueError("Upload at least one PDF before requesting a resource overview.")

        context = self.build_context(resources)
        response = get_llm().invoke(
            [
                SystemMessage(
                    content=(
                        "You summarize only the PDF passages supplied in the user message. "
                        "Do not use external medical knowledge, fill gaps, give clinical advice, or invent citations. "
                        "If the sources are insufficient or inconsistent, say so plainly. "
                        "Write a concise discussion starter with: overall idea, key themes, points of agreement or tension, "
                        "and limitations. Cite claims as [resource_id, p. page]. "
                        f"Respond in the requested presentation language: {language}."
                    )
                ),
                HumanMessage(content=f"USER-UPLOADED PDF PASSAGES:\n{context}"),
            ]
        )
        summary = self._message_text(response).strip()
        if not summary:
            raise ValueError("The model returned an empty resource overview. Please retry.")
        analysis = ResourceAnalysis(
            summary=summary,
            resource_ids=[resource.id for resource in resources],
        )
        return analysis

    def build_context(self, resources: list[Resource]) -> str:
        blocks: list[str] = []
        remaining = self.max_characters
        for resource in resources:
            if remaining <= 0:
                break
            parts: list[str] = []
            used = 0
            for page in resource.extracted_pages:
                page_number = page.get("page")
                text = str(page.get("text") or "").strip()
                if not text:
                    continue
                budget = min(self.max_characters_per_resource - used, remaining - used)
                if budget <= 0:
                    break
                excerpt = text[:budget]
                parts.append(f"[resource_id={resource.id}; page={page_number}]\n{excerpt}")
                used += len(excerpt)
            if parts:
                block = f"RESOURCE: {resource.filename} (ID: {resource.id})\n" + "\n".join(parts)
                blocks.append(block)
                remaining -= len(block)
        if not blocks:
            raise ValueError("No readable text is available in the uploaded PDFs.")
        return "\n\n---\n\n".join(blocks)[: self.max_characters]

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
