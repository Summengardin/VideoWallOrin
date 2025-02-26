import pytest
from unittest.mock import Mock, patch, call
import logging
from typing import Dict

from mqtt_handler import MQTTCommandHandler, Camera, VapixController, CameraFeature
from concurrent.futures import ThreadPoolExecutor

@pytest.fixture
def mock_pipeline():
    pipeline = Mock()
    pipeline.osd_manager = {0: Mock(), 1: Mock()}
    pipeline.sources = {
        0: Mock(camera=Mock(controller=None)),
        1: Mock(camera=Mock(controller=None))
    }
    return pipeline

@pytest.fixture
def cameras() -> Dict[str, Camera]:
    return {}

@pytest.fixture
def handler(mock_pipeline, cameras):
    with ThreadPoolExecutor() as executor:
        return MQTTCommandHandler(mock_pipeline, cameras, executor)

def test_camera_setup(handler, cameras):
    # Test camera initialization sequence
    handler.handle_message("Cameras/CAM1/IP", "192.168.1.100")
    handler.handle_message("Cameras/CAM1/Username", "root")
    handler.handle_message("Cameras/CAM1/Password", "root")
    handler.handle_message("Cameras/CAM1/Type", "AXIS")

    assert "CAM1" in cameras
    assert cameras["CAM1"].ip == "192.168.1.100"
    assert cameras["CAM1"].username == "root"
    assert cameras["CAM1"].type == "AXIS"

def test_camera_feature_validation():
    feature = CameraFeature("test", float, 0.0, 100.0)
    
    assert feature.validate_value("50.0") == 50.0
    assert feature.validate_value("0.0") == 0.0
    assert feature.validate_value("100.0") == 100.0
    
    # Test bounds
    assert feature.validate_value("-10.0") == 0.0
    assert feature.validate_value("200.0") == 100.0
    
    with pytest.raises(ValueError):
        feature.validate_value("invalid")

@patch('requests.Session')
def test_vapix_controller_integration(mock_session, handler, cameras):
    mock_response = Mock()
    mock_response.text = "Success"
    mock_session.return_value.request.return_value = mock_response

    # Setup camera
    handler.handle_message("Cameras/CAM1/IP", "192.168.1.100")
    handler.handle_message("Cameras/CAM1/Username", "root")
    handler.handle_message("Cameras/CAM1/Password", "pass")
    handler.handle_message("Cameras/CAM1/Type", "AXIS")

    assert isinstance(cameras["CAM1"].controller, VapixController)

def test_pipeline_config(handler, mock_pipeline):
    handler.handle_message("VisionControllers/Width", "1920")
    handler.handle_message("VisionControllers/Height", "1080")
    handler.handle_message("VisionControllers/TilerRows", "2")
    handler.handle_message("VisionControllers/TilerColumns", "2")

    assert mock_pipeline.width == 1920
    assert mock_pipeline.height == 1080
    assert mock_pipeline.tiler_rows == 2
    assert mock_pipeline.tiler_columns == 2

def test_source_commands(handler, mock_pipeline):
    # Setup mock source
    source = mock_pipeline.sources[0]
    source.camera.controller = Mock()
    
    # Test zoom
    handler.handle_message("VisionControllers/Tile1/Zoom", "2.0")
    source.camera.controller.set_zoom.assert_called_with(2.0)
    
    # Test exposure
    handler.handle_message("VisionControllers/Tile1/Exposure", "1000")
    source.camera.controller.set_exposure_time.assert_called_with(1000)

def test_error_handling(handler):
    # Test invalid topic
    handler.handle_message("InvalidTopic/Test", "value")
    
    # Test invalid command
    handler.handle_message("Cameras/CAM1/InvalidCommand", "value")
    
    # Test invalid value
    handler.handle_message("VisionControllers/Width", "invalid")

def test_osd_updates(handler, mock_pipeline):
    source = mock_pipeline.sources[0]
    source.camera.controller = Mock()
    osd = mock_pipeline.osd_manager[0]

    handler.handle_message("VisionControllers/Tile1/Zoom", "2.0")
    
    osd.upsert_text.assert_called_with(
        "Zoom: 2.0", "feature", 940, 980, 'c', 36,
        (1.0, 1.0, 1.0, 1.0), (0, 0, 0, 0.6), 2
    )

if __name__ == "__main__":
    pytest.main([__file__])