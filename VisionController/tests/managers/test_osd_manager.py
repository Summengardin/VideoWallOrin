
from VisionController.libs.gst.osd_manager import OSDManager
import time
import pytest

@pytest.fixture
def manager():
    return OSDManager(None)


def test_osd_manager_add_text(manager: OSDManager):
    assert len(manager.osd_text_dicts) == 3
    text = "test"
    x = 0
    y = 0
    font_size = 18
    font_color = (1.0, 1.0, 1.0, 1.0)
    bg_color = (0.0, 0.0, 0.0, 0.6)
    manager.add_text(text, x, y, font_size, font_color, bg_color)

    assert len(manager.osd_text_dicts) == 4
    assert manager.osd_text_dicts[3]["text"] == text
    assert manager.osd_text_dicts[3]["x"] == x
    assert manager.osd_text_dicts[3]["y"] == y
    assert manager.osd_text_dicts[3]["font_size"] == font_size
    assert manager.osd_text_dicts[3]["font_color"] == font_color
    assert manager.osd_text_dicts[3]["bg_color"] == bg_color


def test_osd_manager_add_timeout_text(manager: OSDManager):
    assert len(manager.osd_text_dicts) == 3
    text = "test"
    x = 0
    y = 0
    font_size = 18
    font_color = (1.0, 1.0, 1.0, 1.0)
    bg_color = (0.0, 0.0, 0.0, 0.6)
    timeout = 1
    manager.add_timeout_text(text, x, y, font_size, font_color, bg_color, timeout)

    assert len(manager.osd_text_dicts) == 4
    assert manager.osd_text_dicts[3]["text"] == text
    assert manager.osd_text_dicts[3]["x"] == x
    assert manager.osd_text_dicts[3]["y"] == y
    assert manager.osd_text_dicts[3]["font_size"] == font_size
    assert manager.osd_text_dicts[3]["font_color"] == font_color
    assert manager.osd_text_dicts[3]["bg_color"] == bg_color

    time.sleep(timeout+1) # Add a little delay to make sure the text is removed
    assert len(manager.osd_text_dicts) == 3