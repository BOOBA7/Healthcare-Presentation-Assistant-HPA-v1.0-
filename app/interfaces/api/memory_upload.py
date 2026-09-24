"""Bounded multipart decoding without UploadFile's disk-spooling parser."""

from email import policy
from email.parser import BytesParser

from fastapi import HTTPException, Request

from app.application.services.source_screening import SourceScreening


async def read_pdf_upload(request: Request) -> tuple[str, str, bytes, dict[str, str]]:
    content_type = request.headers.get("content-type", "")
    if "\r" in content_type or "\n" in content_type or not content_type.lower().startswith("multipart/form-data;"):
        raise HTTPException(422, "Expected a multipart source upload.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > SourceScreening.MAX_BYTES + 64 * 1024:
            raise HTTPException(413, "Source files are limited to 20 MB.")
        body.extend(chunk)
    try:
        message = BytesParser(policy=policy.default).parsebytes(
            b"Content-Type: " + content_type.encode("ascii") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
        )
        parts = list(message.iter_parts())
        if message.defects or not 1 <= len(parts) <= 2:
            raise ValueError
        file_parts = [part for part in parts if part.get_param("name", header="content-disposition") == "file"]
        if len(file_parts) != 1:
            raise ValueError
        part = file_parts[0]
        if part.defects or part.is_multipart():
            raise ValueError
        if part.get_content_disposition() != "form-data" or not part.get_filename():
            raise ValueError
        content = part.get_payload(decode=True)
        if not isinstance(content, bytes) or part.defects:
            raise ValueError
        fields = {}
        for field in parts:
            if field is part:
                continue
            name = field.get_param("name", header="content-disposition")
            if (name != "resource_declaration" or field.get_filename()
                    or field.is_multipart() or field.defects):
                raise ValueError
            value = field.get_content()
            if not isinstance(value, str) or len(value) > 200 or name in fields:
                raise ValueError
            fields[name] = value
    except Exception:
        raise HTTPException(422, "Invalid multipart source upload.") from None
    if len(content) > SourceScreening.MAX_BYTES:
        raise HTTPException(413, "Source files are limited to 20 MB.")
    return part.get_filename(), part.get_content_type(), content, fields
