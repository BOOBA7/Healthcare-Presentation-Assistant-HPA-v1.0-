from app.ai.harness.healthcare_harness import HEALTHCARE_HARNESS
from app.ai.prompt_builders.evidence_context_builder import EvidenceContextBuilder
from app.domain.models.presentation import Presentation
from app.domain.models.slide_outline import SlideOutline


class SlidePromptBuilder:
    """
    Builds the prompt used to generate
    a single presentation slide.
    """

    def build(
        self,
        presentation: Presentation,
        outline: SlideOutline,
    ) -> str:
        """
        Build the complete prompt for slide generation.
        """

        context = presentation.context

        resources = EvidenceContextBuilder().for_slide(presentation, outline)

        blueprint = presentation.blueprint

        return f"""
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
PRESENTATION STORY
========================

Storytelling:
{blueprint.storytelling}

Learning Objective:
{blueprint.learning_objective}

Estimated Slides:
{blueprint.target_number_of_slides}

========================
VALIDATED RESOURCES
========================

{resources}

========================
CURRENT SLIDE
========================

Slide Number:
{outline.slide_number}

Title:
{outline.title}

Objective:
{outline.objective}

Reviewer Revision Request:
{outline.reviewer_comments or "None"}


========================
OUTPUT FORMAT
========================

Return exactly ONE SlideSchema object.

Do not return markdown.

Do not return explanations.

Do not wrap the JSON inside code blocks.

========================
TASK
========================

Generate ONLY this slide.

The slide must include:

- A concise scientific title
- A clear learning objective
- 3 to 6 key scientific messages
- Slide content written as concise presentation-ready bullet points
- Detailed speaker notes
- Scientific references actually used
- One or more recommended visuals

Requirements:

- Use ONLY the validated resources.
- Never invent scientific evidence.
- Never invent references.
- Cite only references supported by the provided documents.
- For each reference, include the source resource ID, page number and a short supporting excerpt.
- Adapt the scientific level to the audience.
- Write concise PowerPoint bullet points.
- Speaker notes may be more detailed than the slide itself.
- Keep the presentation clinically relevant.
- Return ONLY structured content matching the expected schema.
""".strip()
