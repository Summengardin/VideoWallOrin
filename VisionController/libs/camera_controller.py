import json
from queue import Queue
from typing import Dict, Any, Callable, Optional, Union, Tuple
from abc import ABC, abstractmethod
import requests
from urllib.parse import urljoin
import json
from dataclasses import dataclass



class CameraController(ABC):
    def __init__(self, ip: str, display_name: str, width: int, height: int, framerate: int, format: str, type: str, uri: str):
        self.ip = ip
        self.display_name = display_name
        self.width = width
        self.height = height
        self.framerate = framerate
        self.format = format
        self.type = type
        self.uri = uri
   
    @abstractmethod
    def set_zoom(self, value: float) -> None:
        pass
        
    @abstractmethod
    def set_brightness(self, value: int) -> None:
        pass
        
    @abstractmethod
    def set_focus(self, value: float) -> None:
        pass
        
    @abstractmethod
    def set_exposure(self, value: float) -> None:
        pass
        
    @abstractmethod
    def set_gain(self, value: float) -> None:
        pass




@dataclass
class ParameterLimits:
    min_value: Union[int, float]
    max_value: Union[int, float]
    step: Union[int, float] = 1

class ValidationError(Exception):
    pass



"""
   /\_/\
  ( o.o )
   > ^ <

VAPIX Camera Controller

"""


class VapixController(CameraController):
    PARAMETER_LIMITS = {
        'zoom': ParameterLimits(0.0, 9999.0, 0.1),
        'brightness': ParameterLimits(0, 100, 1),
        'focus': ParameterLimits(0.0, 9999.0, 0.1),
        'exposure': ParameterLimits(0.0, 100.0, 0.1),
        'gain': ParameterLimits(0.0, 100.0, 0.1),
        'iris': ParameterLimits(0, 9999, 1),
        'speed': ParameterLimits(0, 100, 1)
    }

    def __init__(self, ip: str, display_name: str = "Axis Camera", width: int = 1920, height: int = 1080, 
                 framerate: int = 60, format: str = None, type: str = None, uri: str = None,
                 username: str = "root", password: str = "pass"):
        super().__init__(ip, display_name, width, height, framerate, format, type, uri)
        self.auth = (username, password)
        self.base_url = f"http://{ip}/axis-cgi/"

    def _validate_parameter(self, param: str, value: Union[int, float]) -> None:
        if param not in self.PARAMETER_LIMITS:
            raise ValidationError(f"Unknown parameter: {param}")
        
        limits = self.PARAMETER_LIMITS[param]
        if not (limits.min_value <= value <= limits.max_value):
            raise ValidationError(
                f"Value {value} for {param} out of range [{limits.min_value}, {limits.max_value}]"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        try:
            url = urljoin(self.base_url, endpoint)
            response = requests.get(url, auth=self.auth, params=params, timeout=5)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to communicate with camera: {str(e)}")

    def get_current_position(self) -> Tuple[float, float, float]:
        resp = self._make_request('com/ptz.cgi', params={'query': 'position'}).text
        pan = float(resp.split()[0].split('=')[1])
        tilt = float(resp.split()[1].split('=')[1])
        zoom = float(resp.split()[2].split('=')[1])
        return (pan, tilt, zoom)

    def absolute_move(self, pan: float, tilt: float, zoom: float, speed: float) -> None:
        self._validate_parameter('speed', speed)
        params = {'pan': pan, 'tilt': tilt, 'zoom': zoom, 'speed': speed}
        self._make_request('com/ptz.cgi', params=params)

    def relative_move(self, pan: float, tilt: float, zoom: float, speed: float) -> None:
        self._validate_parameter('speed', speed)
        params = {'rpan': pan, 'rtilt': tilt, 'rzoom': zoom, 'speed': speed}
        self._make_request('com/ptz.cgi', params=params)

    def continuous_move(self, pan_speed: int, tilt_speed: int, zoom_speed: int) -> None:
        params = {
            'continuouspantiltmove': f"{pan_speed},{tilt_speed}",
            'continuouszoommove': zoom_speed
        }
        self._make_request('com/ptz.cgi', params=params)

    def stop_move(self) -> None:
        params = {'continuouspantiltmove': '0,0', 'continuouszoommove': '0'}
        self._make_request('com/ptz.cgi', params=params)

    def center_move(self, x_pos: int, y_pos: int, speed: int) -> None:
        self._validate_parameter('speed', speed)
        params = {'center': f"{x_pos},{y_pos}", 'speed': speed}
        self._make_request('com/ptz.cgi', params=params)

    def area_zoom(self, x_pos: int, y_pos: int, zoom: int, speed: int) -> None:
        self._validate_parameter('speed', speed)
        params = {'areazoom': f"{x_pos},{y_pos},{zoom}", 'speed': speed}
        self._make_request('com/ptz.cgi', params=params)

    def set_preset(self, preset_name: str) -> None:
        params = {'setserverpresetname': preset_name}
        self._make_request('com/ptz.cgi', params=params)

    def goto_preset(self, preset_name: str, speed: float) -> None:
        self._validate_parameter('speed', speed)
        params = {'gotoserverpresetname': preset_name, 'speed': speed}
        self._make_request('com/ptz.cgi', params=params)

    def remove_preset(self, preset_name: str) -> None:
        params = {'removeserverpresetname': preset_name}
        self._make_request('com/ptz.cgi', params=params)

    def set_focus(self, value: float) -> None:
        self._validate_parameter('focus', value)
        params = {'focus': value}
        self._make_request('com/ptz.cgi', params=params)

    def set_autofocus(self, enabled: bool = True) -> None:
        params = {'autofocus': 'on' if enabled else 'off'}
        self._make_request('com/ptz.cgi', params=params)

    def set_iris(self, value: float) -> None:
        self._validate_parameter('iris', value)
        params = {'iris': value}
        self._make_request('com/ptz.cgi', params=params)

    def set_autoiris(self, enabled: bool = True) -> None:
        params = {'autoiris': 'on' if enabled else 'off'}
        self._make_request('com/ptz.cgi', params=params)

    def set_zoom(self, value: float) -> None:
        self._validate_parameter('zoom', value)
        params = {'zoom': value}
        self._make_request('com/ptz.cgi', params=params)

    def set_brightness(self, value: int) -> None:
        self._validate_parameter('brightness', value)
        params = {'brightness': value}
        self._make_request('image/imageproperties.cgi', params=params)

    def set_exposure(self, value: float) -> None:
        self._validate_parameter('exposure', value)
        params = {'exposure': value}
        self._make_request('image/imageproperties.cgi', params=params)

    def set_gain(self, value: float) -> None:
        self._validate_parameter('gain', value)
        params = {'gain': value}
        self._make_request('image/imageproperties.cgi', params=params)

    def get_ptz_available(self) -> bool:
        try:
            response = self._make_request("param.cgi", params={
                "action": "list",
                "group": "Properties.PTZ.PTZ"
            }).text
            return response.strip().split('=')[1].lower() == "yes"
        except (IndexError, KeyError):
            return False

    def get_param(self, param: str) -> str:
        # if param not in self.PARAMETER_LIMITS:
        #     raise ValidationError(f"Unknown parameter: {param}")
        return self._make_request("param.cgi", {"action": "get", "param": param}).text.strip()

    def set_param(self, param: str, value: str) -> None:
        if param not in self.PARAMETER_LIMITS:
            raise ValidationError(f"Unknown parameter: {param}")
        self._make_request("param.cgi", {"action": "update", "param": param, "value": value})

    def get_device_info(self) -> Dict[str, str]:
        return json.loads(self._make_request("basicdeviceinfo.cgi").text)

    def reset_camera(self) -> None:
        self._make_request("restart.cgi")




if __name__ == "__main__":
    controller = VapixController("10.1.3.81", username="root", password="root")
    print(controller.auth)
    print(controller.get_device_info())
    print(controller.get_param("PTZ.ZoomRange"))
