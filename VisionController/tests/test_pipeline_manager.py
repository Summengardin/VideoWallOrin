import pytest
from unittest.mock import MagicMock, patch
from VisionController.libs.camera import Camera
from VisionController.libs.types import SourceType
from VisionController.libs.gst.pipeline_manager import PipelineManager

# Sample configuration for testing
config = {
    'tiler_rows': 2,
    'tiler_cols': 2,
    'width': 1920,
    'height': 1080,
    'batch_size': 4,
    'streammux_config': None
}

@pytest.fixture
def pipeline_manager():
    """Fixture to create a PipelineManager instance."""
    return PipelineManager(config=config)

def test_initialization(pipeline_manager):
    """Test the initialization of the PipelineManager."""
    assert pipeline_manager.config['tiler_rows'] == 2, "Tiler rows not initialized correctly"
    assert pipeline_manager.config['width'] == 1920, "Width not initialized correctly"
    assert len(pipeline_manager.sources) == 4, "Number of sources not initialized correctly"

def test_create_pipeline(pipeline_manager):
    """Test creating a pipeline."""
    pipeline_manager._create_pipeline()
    assert pipeline_manager.pipeline is not None, "Pipeline not created"

def test_create_elements(pipeline_manager):
    """Test creating elements in the pipeline."""
    pipeline_manager._create_pipeline()
    pipeline_manager._create_elements()
    assert len(pipeline_manager.elements) == 4, "Elements not created"
    assert pipeline_manager.streammux is not None, "Streammux not created"
    assert pipeline_manager.tiler is not None, "Tiler not created"
    assert pipeline_manager.nvosd is not None, "Nvosd not created"
    assert pipeline_manager.sink is not None, "Sink not created"

def test_link_elements(pipeline_manager):
    """Test linking elements in the pipeline."""
    pipeline_manager._create_pipeline()
    pipeline_manager._create_elements()
    pipeline_manager._link_elements()
    # Assuming link_elements logs errors on failure, check log outputs

def test_add_remove_source(pipeline_manager):
    """Test adding and removing a source from the pipeline."""
    camera_mock = MagicMock(spec=Camera)
    camera_mock.type = "Basler"
    camera_mock.ip = "192.168.1.1"
    camera_mock.framerate = 30
    
    pipeline_manager._create_pipeline()
    pipeline_manager._create_elements()

    result = pipeline_manager.add_source(0, camera=camera_mock)
    assert result is True, "Source not added"
    assert pipeline_manager.sources[0].active is True, "Source not set as active"
    
    pipeline_manager.remove_source(0)
    assert pipeline_manager.sources[0].bin is None, "Source bin not removed"
    assert pipeline_manager.sources[0].active is False, "Source not set as inactive"

def test_set_exposure_time(pipeline_manager):
    """Test setting exposure time for a source."""
    camera_mock = MagicMock(spec=Camera)
    camera_mock.type = "Basler"
    camera_mock.ip = "192.168.1.1"
    camera_mock.framerate = 30
    
    pipeline_manager._create_pipeline()
    pipeline_manager._create_elements()
    pipeline_manager.add_source(0, camera=camera_mock)

    # Mock arv_camera's get_float_bounds and set_float methods
    arv_camera_mock = MagicMock()
    arv_camera_mock.get_float_bounds.return_value = (100.0, 20000.0)
    pipeline_manager.sources[0].arv_camera = arv_camera_mock

    pipeline_manager.set_exposure_time_source(0, 0.5)
    arv_camera_mock.set_float.assert_called_with("ExposureTime", 10100.0), "Exposure time not set correctly"

def test_set_gain(pipeline_manager):
    """Test setting gain for a source."""
    camera_mock = MagicMock(spec=Camera)
    camera_mock.type = "Basler"
    camera_mock.ip = "192.168.1.1"
    camera_mock.framerate = 30

    pipeline_manager._create_pipeline()
    pipeline_manager._create_elements()
    pipeline_manager.add_source(0, camera=camera_mock)

    arv_camera_mock = MagicMock()
    pipeline_manager.sources[0].arv_camera = arv_camera_mock

    pipeline_manager.set_gain_source(0, 0.5)
    arv_camera_mock.set_float.assert_called_with("Gain", 12.0), "Gain not set correctly"

def test_set_zoom(pipeline_manager):
    """Test setting zoom for a source."""
    camera_mock = MagicMock(spec=Camera)
    camera_mock.type = "Basler"
    camera_mock.ip = "192.168.1.1"
    camera_mock.framerate = 30

    pipeline_manager._create_pipeline()
    pipeline_manager._create_elements()
    pipeline_manager.add_source(0, camera=camera_mock)

    arv_camera_mock = MagicMock()
    pipeline_manager.sources[0].arv_camera = arv_camera_mock

    pipeline_manager.set_zoom_source(0, 0.5)
    arv_camera_mock.set_integer.assert_called_with("Zoom", 500), "Zoom not set correctly"

def test_start_stop_pipeline(pipeline_manager):
    """Test starting and stopping the pipeline."""
    pipeline_manager._create_pipeline()
    pipeline_manager._create_elements()
    pipeline_manager._link_elements()


    pipeline_manager.stop()
    assert pipeline_manager.loop is None, "Pipeline loop not stopped"


