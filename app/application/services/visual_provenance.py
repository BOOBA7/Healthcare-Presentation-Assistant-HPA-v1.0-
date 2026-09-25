"""Deterministic, server-controlled provenance receipts for style and visuals."""

import hashlib
import json

from app.domain.models.presentation import Presentation, StyleProvenance
from app.domain.models.resource import Resource
from app.domain.models.slide import SlideVisual, VisualProvenance


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def style_receipt(presentation: Presentation, template: Resource | None) -> StyleProvenance:
    source = "supplied_template" if presentation.custom_template_id else "hpa_theme"
    original_sha256 = template.metadata.original_sha256 if template else None
    values = {
        "source": source,
        "theme": presentation.theme.value,
        "colour": presentation.colour.value,
        "template_resource_id": presentation.custom_template_id,
        "template_original_sha256": original_sha256,
    }
    return StyleProvenance(
        source=source,
        digest=_digest(values),
        template_resource_id=presentation.custom_template_id,
        template_original_sha256=original_sha256,
    )


def visual_receipt(
    layout: str, visual: SlideVisual | None, resource: Resource | None = None
) -> VisualProvenance:
    source = "none" if visual is None else "reviewed_project_asset" if visual.kind == "image" else "supplied_values"
    asset = None
    if visual is not None and visual.kind == "image" and resource is not None:
        asset = next((item for item in resource.metadata.assets if item.id == visual.asset_id), None)
    values = {
        "layout": layout,
        "visual": visual.model_dump(mode="json") if visual else None,
        "resource_original_sha256": resource.metadata.original_sha256 if resource else None,
        "asset_sha256": asset.sha256 if asset else None,
    }
    return VisualProvenance(
        source=source,
        digest=_digest(values),
        resource_id=visual.resource_id if visual and visual.kind == "image" else None,
        asset_id=visual.asset_id if visual and visual.kind == "image" else None,
        original_sha256=resource.metadata.original_sha256 if resource else None,
        asset_sha256=asset.sha256 if asset else None,
    )
