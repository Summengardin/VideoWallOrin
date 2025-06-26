
from VisionController.libs.camera import Camera
from VisionController.libs.utils import index_dataclass
from VisionController.libs.vw_types import Source, SourceType
from typing import Tuple

class SourceManager:
    def __init__(self, pipeline_manager):
        self.pipeline_manager = pipeline_manager
        self.sources = []
        self.active_source_ips = []

    def add_source(self, source_id: int, camera: Camera = None) -> bool:
        pass

    def remove_source(self, source_id: int) -> bool:
        pass

    def _create_source_bin(self, source_id: int, camera: Camera = None):
        pass

    def _handle_source_config(self, source_id: int, config: dict):
        pass

    def get_exposure_bounds(self, source_id: int) -> Tuple[float, float]:
        pass

    def get_gain_bounds(self, source_id: int) -> Tuple[float, float]:
        pass

    def get_zoom_bounds(self, source_id: int) -> Tuple[int, int]:
        pass
