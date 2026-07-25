from app.ai.harness.healthcare_harness import HEALTHCARE_HARNESS
from app.domain.models.presentation import Presentation


class BlueprintPromptBuilder:
    """
    Builds the prompt used to generate
    the presentation blueprint.
    """

    def build(self, presentation: Presentation) -> str:
        """
        Build the complete prompt for blueprint generation.
        """

        context = presentation.context

        resources = "\n\n".join(
            f"SOURCE ID: {resource.id} | TITLE: {resource.title or resource.filename}\n{(resource.extracted_text or '')[:12000]}"
            for resource in presentation.resources
        )
        review_comments = "\n".join(
            f"- Slide {item.slide_number}: {item.reviewer_comments}"
            for item in (presentation.blueprint.slides if presentation.blueprint else [])
            if item.reviewer_comments
        ) or "None"

        prompt = f"""
{HEALTHCARE_HARNESS}

========================
PRESENTATION CONTEXT
========================

Title:
{presentation.title}

Topic:
{context.topic}

Audience:
{context.audience.value}

Presentation Type:
{context.presentation_type.value}

Language:
{context.language.value}

Duration:
{context.duration_minutes} minutes

Objective:
{context.objective}

========================
VALIDATED RESOURCES
========================

{resources}

REVIEWER REVISION REQUESTS:
{review_comments}

========================
TASK
========================

Create a scientific presentation blueprint.

The blueprint must include:

- Presentation title
- Storytelling strategy
- Learning objectives
- Estimated number of slides
- Ordered list of slides
- Logical scientific progression

For each slide, you MUST provide:

- slide_number
- title
- objective
- key_message

The key_message must represent the single most important idea
that the audience should remember after this slide.

Never omit key_message.

Return only structured content.
"""

        return prompt.strip()
