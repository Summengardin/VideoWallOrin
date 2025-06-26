from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

# from VisionController.libs.gst.pipeline_manager import PipelineManager
from visca_over_ip.camera import Camera as ViscaController
from onvif import ONVIFCamera

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
               

    def set_controller(self, controller : ViscaController) -> bool:
        """ Set the controller for the camera. Compressed cameras (Z3) are controlled through a ViscaController.

        :param controller: The controller to apply to the camera
        :type controller: ViscaController

        :return: True if the controller was set successfully, False otherwise
        :rtype: bool
        """
        if self.type == "Compressed" and isinstance(controller, ViscaController):
            self.visca_controller = controller
        else:
            logger.warning(f"Camera {self.id}: {self.ip}, Invalid controller: {controller}")
            return False
        return True
    

    def set_brightness(self, brightness: float, controller):
        """Sets the brightness of the camera
        :param brightness: 0.0 to 1.0

        :param controller: The controller to apply to the camera
        :type controller: ViscaController for Z3 cameras, PipelineManager for Basler / TheImagingSource cameras, and AxisCamera for Axis cameras

        :return: True if the brightness was set successfully, False otherwise
        :rtype: bool
        """
        if self.type == "Compressed":
            return self.visca_controller.set_brightness(brightness)
        if not isinstance(brightness, float) or brightness < 0.0 or brightness > 1.0:
            raise ValueError('The brightness must be a float between 0.0 and 1.0 inclusive')

        brightness = scale(brightness, to_min=0.0, to_max=1.0)
        brightness = int(brightness * 255)


    def __del__(self):
        if self.visca_controller is not None:
            self.visca_controller.close_connection()




    