"""Conservative PPTX evidence labels; styling never establishes primary evidence."""

PRIMARY_REFERENCE_WARNING = "Source: user-supplied presentation — primary reference unavailable."


def source_warning(resource):
    # No claim-to-primary-source verification workflow exists yet. A DOI, a
    # references slide or a user/model flag cannot establish that relationship.
    return PRIMARY_REFERENCE_WARNING if resource.file_type.value == "pptx" else None


def reference_warnings(references, resources):
    by_id = {resource.id: resource for resource in resources}
    return list(dict.fromkeys(
        warning for reference in references
        if (resource := by_id.get(reference.get("resource_id"))) is not None
        if (warning := source_warning(resource))
    ))


def label_pptx_reference(reference, resource):
    """Replace model bibliography with original-source descriptors only."""
    if not source_warning(resource):
        return
    locator = {key: reference.get(key) for key in ("resource_id", "page", "evidence_excerpt")}
    reference.clear()
    reference.update(locator)
    reference.update(
        title=resource.title or resource.filename,
        source=resource.source,
        year=None,
        location_kind="slide",
        primary_reference_verified=False,
        source_warning=source_warning(resource),
    )
