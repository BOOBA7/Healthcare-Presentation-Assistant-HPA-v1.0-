from pathlib import Path
from uuid import uuid4

from pptx import Presentation as PowerPoint
from pptx.util import Inches, Pt

from app.domain.models.presentation import Presentation


class ExportPowerPointUseCase:
    """Create a PowerPoint file from generated domain slides."""

    def execute(self, presentation: Presentation, output_dir: Path) -> Path:
        if not presentation.slides:
            raise ValueError("Generate presentation slides before exporting PowerPoint.")
        if not presentation.state.presentation_validated:
            raise ValueError("Human approval of the final presentation is required before export.")
        if not presentation.resources or not presentation.state.resources_validated:
            raise ValueError("Validated user resources are required before exporting PowerPoint.")
        if not all(resource.is_validated for resource in presentation.resources):
            raise ValueError("Every resource must be validated by the user before export.")

        output_dir.mkdir(parents=True, exist_ok=True)
        deck = PowerPoint()

        title_slide = deck.slides.add_slide(deck.slide_layouts[0])
        title_slide.shapes.title.text = presentation.title
        title_slide.placeholders[1].text = presentation.context.objective

        for slide in presentation.slides:
            ppt_slide = deck.slides.add_slide(deck.slide_layouts[1])
            ppt_slide.shapes.title.text = slide.title
            frame = ppt_slide.placeholders[1].text_frame
            frame.clear()
            for index, message in enumerate(slide.key_messages or [slide.content]):
                paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
                paragraph.text = message
                paragraph.level = 0
                paragraph.font.size = Pt(20)

            if slide.references:
                textbox = ppt_slide.shapes.add_textbox(Inches(0.5), Inches(6.7), Inches(9), Inches(0.4))
                textbox.text_frame.paragraphs[0].text = "References: " + "; ".join(slide.references)
                textbox.text_frame.paragraphs[0].font.size = Pt(8)

        self._add_resources_slide(deck, presentation)

        path = output_dir / f"{presentation.id}-{uuid4().hex[:8]}.pptx"
        deck.save(path)
        return path

    @staticmethod
    def _add_resources_slide(deck: PowerPoint, presentation: Presentation) -> None:
        """Append the mandatory, human-validated source list to every exported deck."""
        resources_slide = deck.slides.add_slide(deck.slide_layouts[1])
        resources_slide.shapes.title.text = "Ressources et validation"
        frame = resources_slide.placeholders[1].text_frame
        frame.clear()

        heading = frame.paragraphs[0]
        heading.text = "Toutes les ressources ci-dessous ont été validées par l’utilisateur."
        heading.font.size = Pt(20)

        for resource in presentation.resources:
            details = [resource.title or resource.filename]
            if resource.source:
                details.append(resource.source)
            details.append(f"ID : {resource.id}")
            paragraph = frame.add_paragraph()
            paragraph.text = " — ".join(details) + " (validée par l’utilisateur)"
            paragraph.level = 0
            paragraph.font.size = Pt(16)
