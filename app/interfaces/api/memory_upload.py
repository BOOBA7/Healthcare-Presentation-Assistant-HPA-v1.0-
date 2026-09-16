"""Bounded multipart decoding without UploadFile's disk-spooling parser."""

from email import policy
from email.parser import BytesParser

from fastapi import HTTPException, Request

from app.application.services.source_screening import SourceScreening


async def read_pdf_upload(request: Request) -> tuple[str, str, bytes]:
    content_type = request.headers.get("content-type", "")
    if "\r" in content_type or "\n" in content_type or not content_type.lower().startswith("multipart/form-data;"):
        raise HTTPException(422, "Expected a multipart PDF upload.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > SourceScreening.MAX_BYTES + 64 * 1024:
            raise HTTPException(413, "PDF files are limited to 20 MB.")
        body.extend(chunk)
    try:
        message = BytesParser(policy=policy.default).parsebytes(
            b"Content-Type: " + content_type.encode("ascii") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
        )
        parts = list(message.iter_parts())
        if message.defects or len(parts) != 1:
            raise ValueError
        part = parts[0]
        if part.defects or part.is_multipart() or part.get_param("name", header="content-disposition") != "file":
            raise ValueError
        if part.get_content_disposition() != "form-data" or not part.get_filename():
            raise ValueError
        content = part.get_payload(decode=True)
        if not isinstance(content, bytes) or part.defects:
            raise ValueError
    except Exception:
        raise HTTPException(422, "Invalid multipart PDF upload.") from None
    if len(content) > SourceScreening.MAX_BYTES:
        raise HTTPException(413, "PDF files are limited to 20 MB.")
    return part.get_filename(), part.get_content_type(), content
