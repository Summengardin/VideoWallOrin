import logging

logger = logging.getLogger(__name__)

class CameraControl:
    def __init__(self, *args, **kwargs):
        logger.info(f"Not implemented yet for {self.__class__.__name__} class")

    def continuous_zoom(self, zoom_speed: float):
        logger.info(f"Not implemented yet for {self.__class__.__name__} class")

    def continuous_pan(self, pan_speed: float):
        logger.info(f"Not implemented yet for {self.__class__.__name__} class")

    def continuous_tilt(self, tilt_speed: float):
        logger.info(f"Not implemented yet for {self.__class__.__name__} class")

    def absolute_pan(self, pan_position: float):
        logger.info(f"Not implemented yet for {self.__class__.__name__} class")

    def absolute_tilt(self, tilt_position: float):
        logger.info(f"Not implemented yet for {self.__class__.__name__} class")

    def absolute_zoom(self, zoom_position: float):
        logger.info(f"Not implemented yet for {self.__class__.__name__} class")    

    def set_brightness(self, brightness: float):
        logger.info(f"Not implemented yet for {self.__class__.__name__} class")
