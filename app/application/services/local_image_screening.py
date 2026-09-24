"""Optional in-memory macOS OCR/face screening with OS-enforced no-write/no-network.

No fallback to unconfined execution or a file-based OCR wrapper is permitted.
"""
import json
from pathlib import Path
import subprocess
import sys

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.source_metadata import OcrRegion
from app.domain.exceptions.workflow_error import WorkflowError


class ImageInspection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    lines: list[OcrRegion]
    faces: int = Field(ge=0, strict=True)


class LocalImageScreening:
    ENGINE = 'apple-vision-ocr1-face1-en-US-text-only-v1'
    TIMEOUT_SECONDS = 30
    MAX_PIXELS = 16_000_000
    MAX_PAGES = 20
    BINARY = Path(__file__).resolve().parents[2] / 'interfaces/ocr/.build/vision'
    PROFILE = '(version 1)(allow default)(deny file-write*)(deny network*)'

    @staticmethod
    def incomplete():
        return WorkflowError('SOURCE_SCREENING_INCOMPLETE',
                             'Local image screening is unavailable or incomplete. Use a supported dated text PDF. No source was accepted.')

    @classmethod
    def inspect(cls, png: bytes) -> ImageInspection:
        from app.application.services.raster_privacy import screen_raster_text, require_text_only_pixels
        result = cls.inspect_experimental(png)
        screen_raster_text('\n'.join(line.text for line in result.lines))
        require_text_only_pixels(png, result.lines)
        return result

    @classmethod
    def inspect_experimental(cls, png: bytes) -> ImageInspection:
        """Native measurements only; production also requires the text-only pixel gate."""
        if sys.platform != 'darwin' or not cls.BINARY.is_file() or len(png) > 20 * 1024 * 1024:
            raise cls.incomplete()
        try:
            process = subprocess.run(
                ['/usr/bin/sandbox-exec', '-p', cls.PROFILE, str(cls.BINARY)],
                input=png, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=cls.TIMEOUT_SECONDS, check=True,
            )
            if len(process.stdout) > 2_000_000:
                raise cls.incomplete()
            payload = json.loads(process.stdout)
            # Native positions are normalized, top-left-origin rectangles.
            result = ImageInspection.model_validate(payload)
            if not result.lines or len(result.lines) > 10_000:
                raise cls.incomplete()
            return result
        except WorkflowError:
            raise
        except (Exception, KeyboardInterrupt):
            # subprocess.run kills and waits for its child on timeout/interruption.
            raise cls.incomplete() from None
