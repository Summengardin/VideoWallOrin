from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Optional, List, Tuple
import requests
import logging
import time


from ..vw_types import CameraController, CameraControllerError

logger = logging.getLogger(__name__)

class PTZStatus(Enum):
    MOVING = auto()
    STOPPED = auto()
    ERROR = auto()

class ImageFormat(Enum):
    JPEG = "jpeg"
    MJPEG = "mjpeg"
    H264 = "h264"

class VapixController(CameraController):
    def __init__(self, ip: str, username: str, password: str):
        self.ip = ip
        self._session = requests.Session()
        self._session.auth = (username, password)
        self._session.verify = False
        self.base_url = f"http://{ip}/axis-cgi/"
        self.limits = self._get_camera_limits()
        self.ptz_status = PTZStatus.STOPPED
        self._initialize_camera()

    def _initialize_camera(self):
        """Initialize camera with default settings"""
        try:
            # Basic camera setup
            self._make_request("GET", "param.cgi", {
                'action': 'update',
                'Image.I0.Enabled': 'yes',
                'Image.I0.Name': 'View',
                'Image.I0.Source': '0'
            })
        except CameraControllerError as e:
            logger.error(f"Failed to initialize camera: {e}")

    def set_zoom(self, value: float) -> bool:
        """Set absolute zoom position"""
        try:
            value = max(self.limits.min_zoom, min(value, self.limits.max_zoom))
            self._make_request("GET", "com/ptz.cgi", {
                'zoom': value,
                'camera': 1,
                'speed': 50  # Medium speed for smooth movement
            })
            return True
        except CameraControllerError as e:
            logger.error(f"Failed to set zoom: {e}")
            return False

    def set_exposure(self, mode: ExposureMode, value: Optional[float] = None) -> bool:
        """Set exposure mode and optionally exposure time"""
        try:
            params = {
                'camera': 1,
                'exposure': mode.value
            }
            
            if value is not None and mode == ExposureMode.MANUAL:
                value = max(self.limits.min_exposure, min(value, self.limits.max_exposure))
                params['exposure_us'] = value
            
            self._make_request("GET", "com/ptz.cgi", params)
            return True
        except CameraControllerError as e:
            logger.error(f"Failed to set exposure: {e}")
            return False

    def set_gain(self, value: float) -> bool:
        """Set camera gain"""
        try:
            value = max(self.limits.min_gain, min(value, self.limits.max_gain))
            self._make_request("GET", "com/ptz.cgi", {
                'gain': value,
                'camera': 1
            })
            return True
        except CameraControllerError as e:
            logger.error(f"Failed to set gain: {e}")
            return False

    def get_position(self) -> Dict[str, float]:
        """Get current PTZ position"""
        try:
            response = self._make_request("GET", "com/ptz.cgi", {
                'query': 'position',
                'camera': 1
            })
            return self._parse_position(response)
        except CameraControllerError:
            return {}

    def stop(self) -> bool:
        """Stop all PTZ movement"""
        try:
            self._make_request("GET", "com/ptz.cgi", {
                'stop': 1,
                'camera': 1
            })
            self.ptz_status = PTZStatus.STOPPED
            return True
        except CameraControllerError:
            return False

    def reset(self) -> bool:
        """Reset camera to home position"""
        try:
            self._make_request("GET", "com/ptz.cgi", {
                'reset': 1,
                'camera': 1
            })
            return True
        except CameraControllerError:
            return False

    # Additional VAPIX-specific methods
    def set_focus(self, value: Optional[float] = None, auto: bool = True) -> bool:
        """Set focus mode and optionally focus position"""
        try:
            params = {
                'camera': 1,
                'autofocus': 'on' if auto else 'off'
            }
            
            if value is not None and not auto:
                params['focus'] = value
            
            self._make_request("GET", "com/ptz.cgi", params)
            return True
        except CameraControllerError:
            return False

    def set_stream_config(self, format: ImageFormat, resolution: Tuple[int, int], fps: int) -> bool:
        """Configure video stream parameters"""
        try:
            self._make_request("GET", "param.cgi", {
                'action': 'update',
                'Image.I0.Stream.FPS': str(fps),
                'Image.I0.Stream.Format': format.value,
                'Image.I0.Resolution': f"{resolution[0]}x{resolution[1]}"
            })
            return True
        except CameraControllerError:
            return False

    def get_device_info(self) -> Dict[str, str]:
        """Get camera device information"""
        try:
            response = self._make_request("GET", "param.cgi", {
                'action': 'list',
                'group': 'Properties.System,Properties.API.HTTP.Version'
            })
            return self._parse_device_info(response)
        except CameraControllerError:
            return {}

    def _parse_device_info(self, response: str) -> Dict[str, str]:
        info = {}
        for line in response.splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                info[key.strip()] = value.strip()
        return info

    def reboot(self) -> bool:
        """Reboot the camera"""
        try:
            self._make_request("GET", "restart.cgi", {})
            return True
        except CameraControllerError:
            return False

    def get_stream_uri(self, format: ImageFormat = ImageFormat.H264) -> str:
        """Get the URI for the video stream"""

        if self.uri is not None:
            return self.uri
        
        if self.ip is not None:
            if self.username is not None and self.password is not None:
                return f"rtsp://{self.username}:{self.password}@{self.ip}:554/axis-media/media.amp?streamprofile=stream1"
            else:
                return f"rtsp://{self.ip}:554/axis-media/media.amp?streamprofile=stream1"

        return None


    def wait_for_position(self, timeout: int = 10) -> bool:
        """Wait for PTZ movement to complete"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.ptz_status == PTZStatus.STOPPED:
                return True
            time.sleep(0.1)
        return False