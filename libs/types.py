from dataclasses import dataclass 
from enum import Enum

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst


class SourceType(Enum):
    PLACEHOLDER = 0
    TEST = 1
    RTSP = 2
    BAYER = 3


@dataclass
class PipelineConfig:
    rows: int = None
    cols: int = None
    width: int = None
    height: int = None
    sink_element: str = "nv3dsink"
    enable_pipeline: bool = False
    
    def ready(self):
        if not self.width or not self.height or not self.rows or not self.cols:
            return False
        return True 
    
    def max_num_sources(self):
        if not self.rows or not self.cols:
            return 0
        return self.rows * self.cols


@dataclass
class Source:
    id: int = None
    name: str = None
    ip: str = None
    uri: str = None
    type: SourceType = SourceType.PLACEHOLDER
    active: bool = False
    bin: Gst.Bin = None
    eos: bool = False


@dataclass
class Camera:
    id: int = None
    ip: str = None
    uri: str = None
    name: str = None
    type: str = None
    width: int = None
    height: int = None
    format: str = None
    framerate: float = None
    zoom: float = None
    exposure_time: float = None
    exposure_time_auto: int = 2
    gain: float = None
    gain_auto: int = 2