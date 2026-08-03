from pathlib import Path
from uuid import uuid4

from pptx import Presentation as PowerPoint
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

from app.application.validators.evidence_provenance_validator import EvidenceProvenanceValidator
from app.domain.enums.presentation_theme import PresentationTheme
from app.domain.models.presentation import Presentation
from app.domain.models.resource import Resource


THEMES: dict[PresentationTheme, dict[str, tuple[int, int, int]]] = {
    PresentationTheme.CLINICAL: {"primary": (16, 89, 104), "accent": (49, 161, 153), "paper": (245, 250, 250), "ink": (20, 43, 54)},
    PresentationTheme.ACADEMIC: {"primary": (30, 55, 98), "accent": (194, 145, 62), "paper": (248, 248, 252), "ink": (27, 40, 72)},
    PresentationTheme.EXECUTIVE: {"primary": (36, 44, 61), "accent": (209, 113, 75), "paper": (250, 249, 247), "ink": (36, 44, 61)},
    PresentationTheme.MIDNIGHT: {"primary": (15, 23, 42), "accent": (56, 189, 248), "paper": (241, 245, 249), "ink": (15, 23, 42)},
}


class ExportPowerPointUseCase:
    """Export a human-approved presentation in a professional visual theme."""

    def execute(
        self,
        presentation: Presentation,
        output_dir: Path,
        custom_template_path: Path | None = None,
        resources: list[Resource] | None = None,
    ) -> Path:
        resources = resources if resources is not None else presentation.resources
        if not presentation.slides:
            raise ValueError("Generate presentation slides before exporting PowerPoint.")
        if not presentation.state.presentation_validated:
            raise ValueError("Human approval of the final presentation is required before export.")
        if not resources or not presentation.state.resources_validated:
            raise ValueError("Validated user resources are required before exporting PowerPoint.")
        if not all(resource.is_validated for resource in resources):
            raise ValueError("Every resource must be validated by the user before export.")
        if presentation.agenda is None or not presentation.agenda.is_validated:
            raise ValueError("A user-approved agenda is required before exporting PowerPoint.")
        EvidenceProvenanceValidator().validate_presentation(presentation.slides, resources)

        output_dir.mkdir(parents=True, exist_ok=True)
        deck = PowerPoint(custom_template_path) if custom_template_path else PowerPoint()
        if custom_template_path:
            self._remove_template_slides(deck)
        else:
            deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
        palette = THEMES[presentation.theme]

        self._add_title_slide(deck, presentation, palette)
        self._add_agenda_slide(deck, presentation, palette)
        for slide in presentation.slides:
            self._add_content_slide(deck, slide, palette)
        self._add_resources_slide(deck, presentation, resources, palette)

        path = output_dir / f"{presentation.id}-{uuid4().hex[:8]}.pptx"
        deck.save(path)
        return path

    @staticmethod
    def _remove_template_slides(deck: PowerPoint) -> None:
        """Keep the uploaded template's masters/layouts while removing sample slides."""
        while deck.slides:
            relationship_id = deck.slides._sldIdLst[0].rId
            deck.part.drop_rel(relationship_id)
            del deck.slides._sldIdLst[0]

    @staticmethod
    def _blank_layout(deck: PowerPoint):
        return deck.slide_layouts[6] if len(deck.slide_layouts) > 6 else deck.slide_layouts[-1]

    @staticmethod
    def _rgb(value: tuple[int, int, int]) -> RGBColor:
        return RGBColor(*value)

    def _background(self, slide, color: tuple[int, int, int]) -> None:
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = self._rgb(color)

    def _textbox(self, slide, text: str, left: float, top: float, width: float, height: float, *, size: int, color: tuple[int, int, int], bold: bool = False, align=PP_ALIGN.LEFT):
        frame = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height)).text_frame
        frame.clear()
        paragraph = frame.paragraphs[0]
        paragraph.text = text
        paragraph.alignment = align
        paragraph.font.size = Pt(size)
        paragraph.font.bold = bold
        paragraph.font.color.rgb = self._rgb(color)
        return frame

    def _add_title_slide(self, deck: PowerPoint, presentation: Presentation, palette: dict[str, tuple[int, int, int]]) -> None:
        slide = deck.slides.add_slide(self._blank_layout(deck))
        self._background(slide, palette["primary"])
        accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.25), Inches(7.5))
        accent.fill.solid()
        accent.fill.fore_color.rgb = self._rgb(palette["accent"])
        accent.line.fill.background()
        self._textbox(slide, "HEALTHCARE PRESENTATION", 0.8, 1.25, 10.8, 0.35, size=12, color=palette["accent"], bold=True)
        self._textbox(slide, presentation.title, 0.8, 1.8, 11.5, 1.6, size=34, color=(255, 255, 255), bold=True)
        self._textbox(slide, presentation.context.objective, 0.8, 3.75, 10.7, 0.62, size=17, color=(220, 235, 235))
        details = self._title_slide_details(presentation)
        for index, detail in enumerate(details):
            self._textbox(slide, detail, 0.8, 4.55 + index * 0.34, 11.4, 0.28, size=11, color=(220, 235, 235))
        self._textbox(slide, f"{presentation.context.duration_minutes} min  ·  {presentation.context.audience.value}", 0.8, 6.5, 10.0, 0.3, size=11, color=(220, 235, 235))

    @staticmethod
    def _title_slide_details(presentation: Presentation) -> list[str]:
        context = presentation.context
        details: list[str] = []
        presenter = " · ".join(item for item in (context.presenter_name, context.presenter_title) if item)
        location = " · ".join(item for item in (context.venue, context.presentation_date) if item)
        for item in (presenter, context.organization, context.event_name, location):
            if item:
                details.append(item)
        return details[:4]

    def _add_agenda_slide(self, deck: PowerPoint, presentation: Presentation, palette: dict[str, tuple[int, int, int]]) -> None:
        slide = deck.slides.add_slide(self._blank_layout(deck))
        self._background(slide, palette["paper"])
        self._header(slide, self._label(presentation, "Agenda", "Agenda", "جدول الأعمال"), palette)
        for index, item in enumerate(presentation.agenda.items):
            top = 1.55 + index * 0.78
            badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.8), Inches(top), Inches(0.38), Inches(0.38))
            badge.fill.solid()
            badge.fill.fore_color.rgb = self._rgb(palette["accent"])
            badge.line.fill.background()
            self._textbox(slide, str(index + 1), 0.8, top + 0.02, 0.38, 0.25, size=10, color=(255, 255, 255), bold=True, align=PP_ALIGN.CENTER)
            self._textbox(slide, item, 1.4, top - 0.02, 10.7, 0.45, size=20, color=palette["ink"], bold=True)
        self._footer(slide, palette)

    def _add_content_slide(self, deck: PowerPoint, source_slide, palette: dict[str, tuple[int, int, int]]) -> None:
        slide = deck.slides.add_slide(self._blank_layout(deck))
        self._background(slide, palette["paper"])
        self._header(slide, source_slide.title, palette)
        bullet_frame = slide.shapes.add_textbox(Inches(0.85), Inches(1.65), Inches(11.5), Inches(3.85)).text_frame
        bullet_frame.clear()
        for index, message in enumerate(source_slide.key_messages or [source_slide.content]):
            paragraph = bullet_frame.paragraphs[0] if index == 0 else bullet_frame.add_paragraph()
            paragraph.text = message
            paragraph.level = 0
            paragraph.font.size = Pt(22)
            paragraph.font.color.rgb = self._rgb(palette["ink"])
            paragraph.space_after = Pt(13)
        if source_slide.content_origin == "ai_generated" and source_slide.evidence_verified:
            self._add_evidence_box(slide, source_slide.reference_details, palette)
        else:
            self._add_authorship_box(slide, source_slide, palette)
        self._footer(slide, palette, self._content_origin_label(source_slide))

    def _header(self, slide, title: str, palette: dict[str, tuple[int, int, int]]) -> None:
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(1.05))
        bar.fill.solid()
        bar.fill.fore_color.rgb = self._rgb(palette["primary"])
        bar.line.fill.background()
        self._textbox(slide, title, 0.8, 0.29, 11.9, 0.47, size=26, color=(255, 255, 255), bold=True)

    def _footer(self, slide, palette: dict[str, tuple[int, int, int]], provenance: str | None = None) -> None:
        text = "HPA  ·  Human-reviewed scientific presentation"
        if provenance:
            text = f"{text}  ·  {provenance}"
        self._textbox(slide, text, 0.8, 7.08, 11.7, 0.18, size=8, color=palette["ink"])

    def _add_evidence_box(self, slide, references: list[dict[str, object]], palette: dict[str, tuple[int, int, int]]) -> None:
        if not references:
            return
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(5.65), Inches(11.7), Inches(1.15))
        box.fill.solid()
        box.fill.fore_color.rgb = self._rgb((230, 240, 239))
        box.line.color.rgb = self._rgb(palette["accent"])
        frame = box.text_frame
        frame.clear()
        frame.margin_left = Inches(0.14)
        frame.margin_top = Inches(0.08)
        for index, reference in enumerate(references):
            title = str(reference.get("title") or "Source")
            excerpt = " ".join(str(reference.get("evidence_excerpt") or "").split())
            paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            paragraph.text = f"{title} — {reference.get('resource_id')}, p. {reference.get('page')}: « {excerpt} »"
            paragraph.font.size = Pt(7)
            paragraph.font.color.rgb = self._rgb(palette["ink"])

    def _add_authorship_box(self, slide, source_slide, palette: dict[str, tuple[int, int, int]]) -> None:
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(5.82), Inches(11.7), Inches(0.72))
        box.fill.solid()
        box.fill.fore_color.rgb = self._rgb((255, 247, 237))
        box.line.color.rgb = self._rgb(palette["accent"])
        message = (
            "User-authored content · Human-approved"
            if source_slide.content_origin == "user_authored"
            else "User-edited content · Human-approved"
        )
        self._textbox(slide, message, 1.0, 6.04, 11.2, 0.22, size=9, color=palette["ink"], bold=True)

    @staticmethod
    def _content_origin_label(source_slide) -> str:
        # Kept short because it appears on every content slide's footer.
        if source_slide.content_origin == "user_authored":
            return "User-authored · Human-approved"
        if source_slide.content_origin == "user_edited":
            return "User-edited · Human-approved"
        return "AI-generated · Human-approved"

    def _add_resources_slide(
        self,
        deck: PowerPoint,
        presentation: Presentation,
        resources: list[Resource],
        palette: dict[str, tuple[int, int, int]],
    ) -> None:
        # One resource is deliberately a small visual block rather than one
        # long sentence. IDs remain available for audit, but do not compete
        # with the document title during normal reading.
        batches = [resources[index:index + 4] for index in range(0, len(resources), 4)]
        origins = {
            "ai_generated": sum(item.content_origin == "ai_generated" for item in presentation.slides),
            "user_edited": sum(item.content_origin == "user_edited" for item in presentation.slides),
            "user_authored": sum(item.content_origin == "user_authored" for item in presentation.slides),
        }
        title = self._label(presentation, "Resources and validation", "Ressources et validation", "المصادر والاعتماد")
        validated = self._label(
            presentation,
            "All resources below were validated by the user.",
            "Toutes les ressources ci-dessous ont été validées par l’utilisateur.",
            "تم اعتماد جميع المصادر التالية من قبل المستخدم.",
        )
        source_label = self._label(presentation, "Organisation", "Organisme", "الجهة")
        audit_label = self._label(presentation, "Audit ID", "Identifiant d’audit", "معرّف التدقيق")

        for batch_number, batch in enumerate(batches, start=1):
            slide = deck.slides.add_slide(self._blank_layout(deck))
            self._background(slide, palette["paper"])
            suffix = f" ({batch_number}/{len(batches)})" if len(batches) > 1 else ""
            self._header(slide, f"{title}{suffix}", palette)

            if batch_number == 1:
                self._textbox(slide, validated, 0.85, 1.38, 11.5, 0.38, size=15, color=palette["ink"], bold=True)
                provenance = (
                    f"Content provenance: {origins['ai_generated']} AI-generated, "
                    f"{origins['user_edited']} user-edited, {origins['user_authored']} user-authored."
                )
                self._textbox(slide, provenance, 0.85, 1.86, 11.5, 0.3, size=9, color=palette["ink"])
                top = 2.38
            else:
                top = 1.5

            for index, resource in enumerate(batch):
                resource_number = (batch_number - 1) * 4 + index + 1
                item_top = top + index * 0.98
                self._textbox(
                    slide,
                    f"{resource_number}. {resource.title or resource.filename}",
                    0.95,
                    item_top,
                    11.1,
                    0.42,
                    size=13,
                    color=palette["ink"],
                    bold=True,
                )
                if resource.source:
                    self._textbox(
                        slide,
                        f"{source_label}: {resource.source}",
                        1.18,
                        item_top + 0.43,
                        10.9,
                        0.2,
                        size=9,
                        color=palette["ink"],
                    )
                self._textbox(
                    slide,
                    f"{audit_label}: {resource.id}",
                    1.18,
                    item_top + 0.66,
                    10.9,
                    0.18,
                    size=8,
                    color=palette["ink"],
                )
            self._footer(slide, palette)

    @staticmethod
    def _label(presentation: Presentation, english: str, french: str, arabic: str) -> str:
        language = presentation.context.language.value
        return french if language == "French" else arabic if language == "Arabic" else english
