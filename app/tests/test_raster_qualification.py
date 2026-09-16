"""Independent synthetic challenges for the restricted raster privacy gate."""
from io import BytesIO
import pytest
from PIL import Image, ImageDraw
from app.application.services.raster_privacy import require_text_only_pixels, screen_raster_text
from app.domain.models.source_metadata import OcrRegion
from app.domain.exceptions.workflow_error import WorkflowError


def test_unlabelled_name_and_benign_text():
    with pytest.raises(WorkflowError):
        screen_raster_text('Alice Example')
    screen_raster_text('Synthetic teaching evidence\nPublication date: 2024')


@pytest.mark.parametrize('graphic', ['face', 'stamp', 'color'])
def test_unrecognized_visual_surface_cannot_pass_text_boxes(graphic):
    image = Image.new('RGB', (300, 300), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), 'Synthetic text', fill='black')
    if graphic == 'face':
        draw.ellipse((80, 100, 220, 250), outline='black', width=3)
    elif graphic == 'stamp':
        draw.rectangle((100, 120, 180, 180), fill='black')
    else:
        draw.text((15, 15), 'color', fill='red')
    output = BytesIO()
    image.save(output, format='PNG')
    line = OcrRegion(text='Synthetic text', box=(0, 0, 0.8, 0.2), confidence=0.5)
    with pytest.raises(WorkflowError):
        require_text_only_pixels(output.getvalue(), [line])


def test_public_heading_is_a_measured_false_positive():
    # Deliberately retained overblocking evidence, not relabelled as an identifier.
    with pytest.raises(WorkflowError) as error:
        screen_raster_text('Learning Objectives')
    assert error.value.code == 'POSSIBLE_IDENTIFIER_DETECTED'
