from dataclasses import dataclass

# from VisionController.libs.gst.pipeline_manager import PipelineManager
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

    visca_controller: ViscaController = None
    
    def update_setting(self, setting: str, value):
        """ Update a setting of the camera. For now, aravis cameras (Basler and TheImagingSource) have to update all features to update any. 
         
        :param setting: The setting to update
        :param value: The value to set the setting to
          
        :raises ValueError: If the value is not valid for the setting
        """
        if hasattr(self, setting):
            try:
                setattr(self, setting, value)
                print(f"Camera {self.id}: {self.ip}, Updated setting: {setting} to: {value}")
            except ValueError:
                logger.warning(f"Camera {self.id}: {self.ip}, Invalid value: {value} for setting: {setting}")
                return False
            except TypeError:
                logger.warning(f"Camera {self.id}: {self.ip}, Invalid value: {value} for setting: {setting}")
                return False
        else:
            logger.warning(f"Camera {self.id}: {self.ip}, Invalid setting: {setting}")
            return False
    

        if self.type == "Compressed" and self.visca_controller is not None:
            if setting == "exposure_time_auto":
                value = 0 if value == 1 else 3
                self.exposure_time_auto = value
                modes = {0: "auto", 1: "manual", 2: "iris priority", 3: "shutter priority"}
                self.visca_controller.autoexposure_mode(modes[value])
            elif setting == "exposure_time":
                value = int(value/10000 * 21)
                self.exposure_time = value
                try:
                    self.visca_controller.set_shutter(value)
                except:
                    pass
            elif setting == "gain":
                value = int(value/100 * 14 + 1)
                self.gain = value
                try:
                    self.visca_controller.set_gain(value)
                except:
                    pass
            elif setting == "zoom":
                value = value/1000 # percent
                self.zoom = value
                try:
                    self.visca_controller.zoom_to(value)
                except:
                    pass
            else:
                return False

            return True
            

    def set_controller(self, controller : ViscaController) -> bool:
        """ Set the controller for the camera. Basler and TheImagingSource cameras are controlled through gstremer and therebyer the a PipelineManager. Compressed cameras (Z3) are controlled through a ViscaController.

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
    

    def __del__(self):
        if self.visca_controller is not None:
            self.visca_controller.close_connection()
    