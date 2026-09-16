"""Explicit dated synthetic fixtures; never patch or bypass application gates."""

import json
import fitz

from app.application.services.source_document import SourceDocument


def dated_resource(**kwargs):
    """Create actual synthetic PDF bytes; all evidence is derived by real controls."""
    texts = {page["page"]: page["text"] for page in kwargs.get("extracted_pages", [])}
    if not texts:
        texts[1] = kwargs.get("extracted_text") or "Synthetic fixture evidence"
    texts[1] = (texts.get(1, "") + "\nPublication date: 2024").strip()
    with fitz.open() as document:
        for number in range(1, max(texts) + 1):
            text = texts.get(number, "Synthetic fixture pagination.")
            width = max(600, max(len(line) for line in text.splitlines()) * 8 + 150)
            height = max(800, len(text.splitlines()) * 16 + 150)
            document.new_page(width=width, height=height).insert_text((72, 72), text)
        document.set_metadata({"title": kwargs.get("title") or kwargs["filename"], "author": kwargs.get("source") or ""})
        resource = SourceDocument.read(kwargs["filename"], document.tobytes(), kwargs["id"])
    if "is_validated" in kwargs:
        resource.is_validated = kwargs["is_validated"]
    return resource


def seed_legacy_sources(repository, state, user_id, project_id):
    """Represent historical rows created before originals were retained."""
    with repository._connect() as connection:
        for resource in state.resource_library:
            metadata = resource.model_dump(mode="json", exclude={"extracted_pages", "extracted_text"})
            connection.execute(
                "INSERT INTO project_resources (user_id, project_id, resource_id, metadata_json, content_hash) VALUES (?, ?, ?, ?, ?)",
                (user_id, project_id, resource.id, json.dumps(metadata), "legacy"),
            )
            connection.executemany(
                "INSERT INTO project_resource_pages VALUES (?, ?, ?, ?, ?)",
                [(user_id, project_id, resource.id, page["page"], page["text"]) for page in resource.extracted_pages],
            )
