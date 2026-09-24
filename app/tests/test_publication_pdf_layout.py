import fitz

from app.application.services.source_document import SourceDocument


def test_publication_vector_layout_and_hyperlink_are_accepted():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 40), "Publication date: 2024")
    page.insert_text((72, 72), "Public scientific guideline")
    page.draw_line((72, 82), (420, 82))
    page.insert_link({
        "kind": fitz.LINK_URI,
        "from": fitz.Rect(72, 90, 220, 110),
        "uri": "https://example.org/guideline",
    })
    content = document.tobytes()
    document.close()

    resource = SourceDocument.read("guideline.pdf", content, "public-guideline")

    assert resource.extracted_text
    assert resource.metadata.original_sha256


def test_optional_asset_failure_does_not_reject_readable_pdf(monkeypatch):
    from app.application.services import source_assets
    from app.domain.exceptions.workflow_error import WorkflowError

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 40), "Publication date: 2024")
    page.insert_text((72, 72), "Readable scientific evidence")
    content = document.tobytes()
    document.close()

    def fail(*args, **kwargs):
        raise WorkflowError("ASSET_INTEGRITY_FAILED", "Optional derivative failed.")

    monkeypatch.setattr(source_assets, "pdf_assets", fail)
    resource = SourceDocument.read("evidence.pdf", content, "evidence")

    assert resource.extracted_text
    assert resource.metadata.assets == []
