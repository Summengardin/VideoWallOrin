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
    

    def __del__(self):
        if self.visca_controller is not None:
            self.visca_controller.close_connection()
    