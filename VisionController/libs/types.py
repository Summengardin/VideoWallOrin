from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional
import requests
import logging

import gi
gi.require_version('Gst', '1.0')
gi.require_version('Aravis', '0.8')
from gi.repository import Gst, Aravis


from .camera import Camera


class SourceType(Enum):
    PLACEHOLDER = 0
    TEST = 1
    RTSP = 2
    BAYER = 3

@dataclass
class Source:
    id: int = None
    cam_id: int = None
    name: str = None
    ip: str = None
    uri: str = None
    type: SourceType = SourceType.PLACEHOLDER
    active: bool = False
    bin: Gst.Bin = None
    eos: bool = False
    camera: Camera = None
    arv_camera: Aravis.Camera = None
    enabled: bool = False
    limits: dict = None




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



class CameraControllerError(Exception):
    pass



class CameraController(ABC):
    @abstractmethod
    def set_zoom(self, value: float) -> bool:
        pass
    
    @abstractmethod
    def set_exposure(self, mode: ExposureMode, value: Optional[float] = None) -> bool:
        pass
    
    @abstractmethod
    def set_gain(self, value: float) -> bool:
        pass

    @abstractmethod
    def get_position(self) -> Dict[str, float]:
        pass

    @abstractmethod
    def stop(self) -> bool:
        pass

    @abstractmethod
    def reset(self) -> bool:
        pass


# @dataclass
# class Camera:
#     id: int = None
#     ip: str = None
#     uri: str = None
#     name: str = None
#     type: str = None
#     width: int = None
#     height: int = None
#     format: str = None
#     framerate: float = None
#     zoom: int = None
#     has_zoom: bool = False
#     exposure_time: float = None
#     exposure_time_auto: int = 2
#     gain: float = None
#     gain_auto: int = 2

#     controller = None
    
#     def update_setting(self, setting: str, value):
#         raise NotImplementedError("Must be implemented by subclasses")






    # def update_camera_features(self):
    #     if self.bin is None or self.camera is None:
    #         print("Camera or bin is None")
    #         return
        
    #     if self.camera.type == SourceType.BAYER:
    #         src = self.bin.get_by_name(f"source-{self.ip}")
    #         if src is None:
    #             return

    #         self._update_camera_features_aravis(src)

    #     elif self.camera.type == SourceType.RTSP:
    #         ip = self.camera.ip
    #         self._update_camera_features_rtsp(ip)
         

    # def _update_camera_features_aravis(self, src):
    #     if self.camera.exposure_time_auto is not None:
    #         src.set_property("exposure-auto", self.camera.exposure_time_auto)
    #     if self.camera.exposure_time is not None and self.camera.exposure_time_auto == 0:
    #         src.set_property("exposure", self.camera.exposure_time)
    #     if self.camera.gain_auto is not None:
    #         src.set_property("gain-auto", self.camera.gain_auto)
    #     if self.camera.gain is not None and self.camera.gain_auto == 0:
    #         src.set_property("gain", self.camera.gain)  
    #     if self.camera.has_zoom and self.camera.zoom is not None:
    #         src.set_property("features", f"Zoom={self.camera.zoom} ExposureTime={self.camera.exposure_time} Gain={self.camera.gain}")
    #         actual = src.get_property("features")    

        