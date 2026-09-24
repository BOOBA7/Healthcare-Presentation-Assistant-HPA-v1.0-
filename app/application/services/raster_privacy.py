"""Conservative text-only raster subset; unrecognized marks are incomplete.

This rejects graphics, faces, stamps and noise outside OCR text regions. It is
not a general image anonymizer or a calibrated name/face classifier.
"""
from io import BytesIO
from PIL import Image, ImageDraw, ImageChops

from app.domain.exceptions.workflow_error import WorkflowError


def screen_raster_text(text):
    """Return advisory findings without refusing a source or OCR correction."""
    from app.application.services.resource_privacy_policy import ResourcePrivacyPolicy
    return ResourcePrivacyPolicy.analyze(text)


def require_text_only_pixels(png, lines):
    with Image.open(BytesIO(png)) as image:
        image.load()
        rgb = image.convert('RGB')
        # Colored pixels are outside this qualified monochrome-text subset.
        red, green, blue = rgb.split()
        if ImageChops.difference(red, green).getextrema()[1] > 8 or ImageChops.difference(red, blue).getextrema()[1] > 8:
            raise WorkflowError('SOURCE_SCREENING_INCOMPLETE', 'Only monochrome text-only raster sources can be screened. Graphics and other visual content are unsupported.')
        mask = Image.new('L', image.size, 255)
        draw = ImageDraw.Draw(mask)
        for line in lines:
            x0, y0, x1, y1 = line.box
            # Bounded allowance for glyph-edge rounding, not large blank regions.
            draw.rectangle((int(x0 * image.width) - 2, int(y0 * image.height) - 2,
                            int(x1 * image.width) + 2, int(y1 * image.height) + 2), fill=0)
        dark = rgb.convert('L').point(lambda value: 255 if value < 245 else 0)
        if ImageChops.multiply(dark, mask).getbbox() is not None:
            raise WorkflowError('SOURCE_SCREENING_INCOMPLETE', 'Unrecognized visual content remains outside OCR text regions. Replace this source with a text-only version.')
