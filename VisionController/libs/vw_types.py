from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Any
import requests
import logging
import threading
import gi
gi.require_version('Gst', '1.0')
# gi.require_version('Aravis', '0.8')
from gi.repository import Gst#, Aravis


class SourceType(Enum):
    PLACEHOLDER = 0
    TEST = 1
    RTSP = 2
    BAYER = 3

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
    control: Any = None


@dataclass
class Source:
    id: int = None
    cam_id: int = None
    name: str = None
    ip: str = None
    uri: str = None
    type: str = "Placeholder"
    active: bool = False
    bin: Gst.Bin = None
    eos: bool = False
    camera: Camera = None
    # arv_camera: Aravis.Camera = None
    enabled: bool = False
    limits: dict = None
    in_removing_state: bool = False
    is_adding_state: bool = False   
    lock: threading.Lock = threading.Lock() 
    control = None

@dataclass
class CameraConfig:
    id: int = None
    ip: str = None
    uri: str = None
    name: str = None
    type: str = None
    width: int = None
    height: int = None
    format: str = None
    framerate: float = None
    exposure_time_auto: int = 2
    exposure_time: float = None
    gain_auto: int = 2
    gain: float = None
    has_zoom: bool = False





class ExposureMode(Enum):
    AUTO = "auto"
    MANUAL = "manual"
    HOLD = "hold"

@dataclass
class CameraLimits:
    min_zoom: float
    max_zoom: float
    min_exposure: float
    max_exposure: float
    min_gain: float
    max_gain: float



        