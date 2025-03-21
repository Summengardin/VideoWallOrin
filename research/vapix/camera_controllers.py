from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, TypeVar, Generic
import requests
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T', int, float, bool)

class CameraError(Exception):
    pass

class ExposureMode(Enum):
    AUTO = "auto"
    MANUAL = "manual"
    HOLD = "hold"

@dataclass
class FeatureRange(Generic[T]):
    min_val: T
    max_val: T
    step: T = None

    def clamp(self, value: T) -> T:
        return max(self.min_val, min(self.max_val, value))

@dataclass
class CameraCapabilities:
    has_zoom: bool = False
    has_focus: bool = False
    has_auto_focus: bool = False
    zoom_range: Optional[FeatureRange[float]] = None
    focus_range: Optional[FeatureRange[float]] = None
    exposure_range: Optional[FeatureRange[float]] = None
    gain_range: Optional[FeatureRange[float]] = None

class CameraController(ABC):
    def __init__(self, ip: str):
        self.ip = ip
        self._capabilities = self._init_capabilities()

    @abstractmethod
    def _init_capabilities(self) -> CameraCapabilities:
        pass

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
    def set_focus(self, value: Optional[float] = None, auto: bool = True) -> bool:
        pass

    @abstractmethod
    def reset(self) -> bool:
        pass

    @property
    def capabilities(self) -> CameraCapabilities:
        return self._capabilities

class VapixController(CameraController):
    def __init__(self, ip: str, username: str, password: str):
        self.username = username
        self.password = password
        self._session = self._init_session()
        super().__init__(ip)

    def _init_session(self) -> requests.Session:
        session = requests.Session()
        session.auth = (self.username, self.password)
        session.verify = False
        return session

    def _init_capabilities(self) -> CameraCapabilities:
        try:
            params = self._make_request("GET", "param.cgi", {
                'action': 'list',
                'group': 'Properties.PTZ.Limits'
            })
            return self._parse_capabilities(params)
        except CameraError:
            return CameraCapabilities()

    def _make_request(self, method: str, endpoint: str, params: Dict = None) -> str:
        url = f"http://{self.ip}/axis-cgi/{endpoint}"
        try:
            response = self._session.request(method, url, params=params, timeout=5)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            raise CameraError(f"VAPIX request failed: {e}")

    def set_zoom(self, value: float) -> bool:
        if not self.capabilities.has_zoom:
            return False
        
        try:
            value = self.capabilities.zoom_range.clamp(value)
            self._make_request("GET", "com/ptz.cgi", {
                'zoom': value,
                'camera': 1
            })
            return True
        except CameraError as e:
            logger.error(f"Failed to set zoom: {e}")
            return False

    def set_exposure(self, mode: ExposureMode, value: Optional[float] = None) -> bool:
        try:
            params = {'camera': 1, 'exposure': mode.value}
            if value is not None and mode == ExposureMode.MANUAL:
                value = self.capabilities.exposure_range.clamp(value)
                params['exposure_us'] = value
            
            self._make_request("GET", "com/ptz.cgi", params)
            return True
        except CameraError as e:
            logger.error(f"Failed to set exposure: {e}")
            return False

    def set_gain(self, value: float) -> bool:
        try:
            value = self.capabilities.gain_range.clamp(value)
            self._make_request("GET", "com/ptz.cgi", {
                'gain': value,
                'camera': 1
            })
            return True
        except CameraError as e:
            logger.error(f"Failed to set gain: {e}")
            return False

    def set_focus(self, value: Optional[float] = None, auto: bool = True) -> bool:
        if not self.capabilities.has_focus:
            return False

        try:
            params = {
                'camera': 1,
                'autofocus': 'on' if auto else 'off'
            }
            
            if value is not None and not auto:
                value = self.capabilities.focus_range.clamp(value)
                params['focus'] = value
            
            self._make_request("GET", "com/ptz.cgi", params)
            return True
        except CameraError as e:
            logger.error(f"Failed to set focus: {e}")
            return False

    def reset(self) -> bool:
        try:
            self._make_request("GET", "com/ptz.cgi", {
                'reset': 1,
                'camera': 1
            })
            return True
        except CameraError:
            return False
        


class ViscaController(CameraController):
    def __init__(self, ip: str, port: int):
        self.controller = ViscaController(ip, port)
    
    def set_zoom(self, value: float) -> bool:
        return self.controller.zoom_to(value)
    
    def set_exposure(self, value: float) -> bool:
        return self.controller.set_shutter(int((1 - value) * 21))
    
    def set_gain(self, value: float) -> bool:
        return self.controller.set_gain(int(value * 14 + 1))





# class OnvifController(CameraController):
#     def __init__(self, ip: str, username: str, password: str):
#         self.camera = ONVIFCamera(ip, 80, username, password)
    
#     def set_zoom(self, value: float) -> bool:
#         return self.camera.set_zoom_position(value)
    
    # Similar implementations for other methods