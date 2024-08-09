from dataclasses import dataclass

from .gst.pipeline_manager import PipelineManager
from visca_over_ip.camera import Camera as ViscaController


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

    pipeline_manager: PipelineManager = None
    visca_controller: ViscaController = None
    
    def update_setting(self, setting: str, value):
        """ Update a setting of the camera. For now, aravis cameras (Basler and TheImagingSource) have to update all features to update any. 
         
        :param setting: The setting to update
        :param value: The value to set the setting to
          
        :raises ValueError: If the value is not valid for the setting
        """
        if hasattr(self, setting):
            attr_type = getattr(self, setting).__class__
            try:
                value = attr_type(value)
            except ValueError:
                logger.warning(f"Camera {self.id}: {self.ip}, Invalid value: {value}")
                return False
            setattr(self, setting, value)
        else:
            logger.warning(f"Camera {self.id}: {self.ip}, Invalid setting: {setting}")
            return False
        
        if (self.type == "Basler" or self.type == "TheImagingSource") and self.pipeline_manager is not None:
            setting_dict = {"ExposureTimeAuto": self.exposure_time_auto,
                        "ExposureTime": self.exposure_time,
                        "GainAuto": self.gain_auto,
                        "Gain": self.gain}
            if self.has_zoom:
                setting_dict["Zoom"] = self.zoom
            
            return self.pipeline_manager.update_camera_feature(self.ip, setting_dict)

        elif self.type == "Compressed" and self.visca_controller is not None:
            if setting == "exposure_time_auto":
                self.exposure_time_auto = value
                modes = {0: "auto", 1: "manual", 2: "iris priority", 3: "shutter priority"}
                self.visca_controller.autoexposure_mode(modes[value])
            elif setting == "exposure_time":
                self.exposure_time = value
                self.visca_controller.set_shutter(value)
            elif setting == "gain":
                self.gain = value
                self.visca_controller.set_gain(value)
            elif setting == "zoom":
                self.zoom = value
                self.visca_controller.zoom_to(value)
            else:
                return False

            return True
            

    def set_controller(self, controller: ViscaController | PipelineManager) -> bool:
        """ Set the controller for the camera. Basler and TheImagingSource cameras are controlled through gstremer and therebyer the a PipelineManager. Compressed cameras (Z3) are controlled through a ViscaController.

        :param controller: The controller to apply to the camera
        :type controller: ViscaController | PipelineManager
        :return: True if the controller was set successfully, False otherwise
        :rtype: bool
        """
        if isinstance(controller, ViscaController) and self.type == "Compressed":
            self.visca_controller = controller
        elif isinstance(controller, PipelineManager) and self.type == "Basler" or self.type == "TheImagingSource":
            self.pipeline_manager = controller
        else:
            logger.warning(f"Camera {self.id}: {self.ip}, Invalid controller: {controller}")
            return False
        return True