
import time
import pytest
# from threading import Thread

from VisionController.libs.gst.osd_manager import OSDManager


@pytest.fixture(scope="function")
def manager():
    """Fixture to create a new OSDManager instance for each test."""
    return OSDManager()

def test_initial_state(manager: OSDManager):
    """Test the initial state of OSDManager."""
    assert len(manager.osd_text_dicts) == 3, "Initial osd_text_dicts should contain 3 items"
    assert len(manager.tiles) == 4, "There should be 4 tiles"
    assert manager.tiles[2]["texts"][1]["text"] == "UPPER MID", "Tile 2, Spot 1 text should be 'UPPER MID'"
    assert manager.tiles[0]["texts"][2]["text"] == "UPPER RIGHT", "Tile 0, Spot 2 text should be 'UPPER RIGHT'"
    assert manager.window_size == (1920, 1080), "Default window size should be 1920x1080"

def test_add_text(manager: OSDManager):
    """Test adding a text entry to osd_text_dicts."""
    initial_length = len(manager.tiles[0]["texts"])
    text = "New Text"
    x, y = 100, 100
    font_size = 24
    font_color = (0.5, 0.5, 0.5, 1.0)
    bg_color = (0.1, 0.1, 0.1, 0.5)
    
    manager.add_text(0, text, x, y, font_size, font_color, bg_color)
    
    assert len(manager.tiles[0]["texts"]) == initial_length + 1, "osd_text_dicts should have one more item"
    new_entry = manager.tiles[0]["texts"][-1]
    assert new_entry["text"] == text, "New text should match the input"
    assert new_entry["x"] == x, "X coordinate should match"
    assert new_entry["y"] == y, "Y coordinate should match"
    assert new_entry["font_size"] == font_size, "Font size should match"
    assert new_entry["font_color"] == font_color, "Font color should match"
    assert new_entry["bg_color"] == bg_color, "Background color should match"

def test_add_timeout_text(manager: OSDManager):
    """Test adding a timeout text entry to osd_text_dicts."""
    initial_length = len(manager.tiles[0]["texts"])
    text = "Timeout Text"
    x, y = 150, 150
    font_size = 20
    font_color = (0.3, 0.3, 0.3, 1.0)
    bg_color = (0.2, 0.2, 0.2, 0.6)
    timeout = 2  # seconds
    
    manager.add_timeout_text(0, text, x, y, font_size, font_color, bg_color, timeout)
    
    assert len(manager.tiles[0]["texts"]) == initial_length + 1, "osd_text_dicts should have one more item"
    new_entry = manager.tiles[0]["texts"][-1]
    assert new_entry["text"] == text, "New text should match the input"
    assert new_entry["timeout"] > time.time(), "Timeout should be set in the future"
    
    # Wait for timeout to expire
    time.sleep(timeout + 1)
    # manager._update_texts()
    assert len(manager.tiles[0]["texts"]) == initial_length, "Timeout text should be removed after expiration"

def test_tile_updates(manager: OSDManager):
    """Test that the tile texts are updated periodically."""
    initial_text = manager.get_tile(1)["texts"][0]["text"]
    manager.set_text(1, 0, "New Text")
    time.sleep(1.5)  # Wait for a couple of updates to occur
    updated_text = manager.get_tile(1)["texts"][0]["text"]
    
    assert initial_text != updated_text, "Tile text should be updated"
    assert updated_text == "New Text", "Tile text should be updated to 'New Text'"

def test_multiple_timeout_texts(manager: OSDManager):
    """Test adding multiple timeout texts and their expiration."""
    tile_num = 0
    initial_length = len(manager.tiles[tile_num]["texts"])
    text1 = "Timeout Text 1"
    text2 = "Timeout Text 2"
    x, y = 100, 100
    font_size = 18
    font_color = (1.0, 0.0, 0.0, 1.0)
    bg_color = (0.0, 0.0, 0.0, 0.6)
    timeout1 = 2
    timeout2 = 4
    
    manager.add_timeout_text(tile_num, text1, x, y, font_size, font_color, bg_color, timeout1)
    manager.add_timeout_text(tile_num, text2, x, y, font_size, font_color, bg_color, timeout2)
    
    assert len(manager.tiles[tile_num]["texts"]) == initial_length + 2, "Two timeout texts should be added"
    
    time.sleep(timeout1 + 1)
    assert len(manager.tiles[tile_num]["texts"]) == initial_length + 1, "First timeout text should be removed"
    
    time.sleep(timeout2 - timeout1 + 1)
    assert len(manager.tiles[tile_num]["texts"]) == initial_length, "Both timeout texts should be removed"

def test_get_tile(manager: OSDManager):
    """Test retrieving a specific tile."""
    texts = manager.get_tile(0)["texts"]
    assert isinstance(texts, list), "Tile should be a list"
    assert texts[2]["text"] == "UPPER RIGHT", "Text for tile[2] should be 'UPPER RIGHT'"


# def test_add_triangle(manager: OSDManager):
#     """Test adding a triangle to the OSD."""
#     manager.add_triangle(0, 960, 540, 100, 10, (1.0, 0.0, 0.0, 1.0), 0)

#     assert len(manager.tiles[0]["triangles"]) == 2, "Triangle should be added"

#     triangle = manager.get_tile(0)["triangles"][1]

#     actual_triangle = {
#         "vertices": [


#     assert triangle["x"] == 960, "X coordinate should match"
#     assert triangle["y"] == 540, "Y coordinate should match"
#     assert triangle["width"] == 100, "Width should match"
#     assert triangle["height"] == 10, "Height should match"
#     assert triangle["color"] == (1.0, 0.0, 0.0, 1.0), "Color should match"
#     assert triangle["timeout"] == 0, "Timeout should be 0"



def test_thread_cleanup(manager: OSDManager):
    """Test that the background thread stops when OSDManager is deleted."""

    assert manager.update_thread.is_alive(), "Update thread should be running"
    manager.stop()
    # del manager
    time.sleep(2)  # Allow some time for the thread to stop
    assert not manager.update_thread.is_alive(), "Update thread should stop after manager is deleted"


