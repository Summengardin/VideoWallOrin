from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

# from VisionController.libs.gst.pipeline_manager import PipelineManager
# from visca_over_ip.camera import Camera as ViscaController
# from onvif import ONVIFCamera

import logging
logger = logging.getLogger(__name__)




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
    zoom: int = None
    has_zoom: bool = False
    exposure_time: float = None
    exposure_time_auto: int = 2
    gain: float = None
    gain_auto: int = 2
    provider: Dict[str, str] = None




    