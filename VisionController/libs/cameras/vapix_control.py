import time
import logging

import sys
sys.path.append('/app/VisionController/libs')

from vapix_python.VapixAPI import VapixAPI
from utils import clamp, scale


logger = logging.getLogger(__name__)

class CameraControl:
    def __init__(self, camera, username='root', password='root', port=80):
        logger.debug(f"Initializing CameraControl for {camera.ip}")
        self.vapix_control = VapixAPI(camera.ip, username, password, port)
        self.ptz = self.vapix_control.ptz
        self.optics = self.vapix_control.optics
        self.imaging = self.vapix_control.imaging
        
        ''' VAPIX CAMERA CONTROL INTERNALS '''
        # If mechanical PTZ is available, then optics is not available.
        self._use_optics = self.optics.is_available()
        if self._use_optics:
            self._capabilities = self.optics.get_capabilities()  
            self._max_magnification = self._capabilities['data']['optics'][0]['maxMagnification']
            self._current_magnification = 1.0 # 0 to 100
        


    def continuous_zoom(self, zoom_speed: float):
        zoom_level = clamp(zoom_speed, -1.0, 1.0) # 0 - 100

        if self._use_optics:
            self._current_magnification += zoom_speed         
            self._current_magnification = clamp(scale(self._current_magnification, 1, self._max_magnification), 1, self._max_magnification)
            self.optics.set_magnification(optics_id=0, magnification=self._current_magnification)
        else:
            zoom_level = scale(zoom_level, from_min=-1.0, from_max=1.0, to_min=-100, to_max=100)
            self.ptz.continuous_zoom(zoom_speed=zoom_level)

    def continuous_pan(self, pan_speed: float):
        if not self.ptz.is_available:
            logger.debug("Camera has no pan-features")
        pan_speed = clamp(pan_speed, -1.0, 1.0) # -100% - +100%
        pan_speed = scale(pan_speed, -1.0, 1.0, -100, 100)
        self.ptz.continuous_pantilt(pan_speed, 0);

    def continuous_tilt(self, tilt_speed: float):
        if not self.ptz.is_available:
            logger.debug("Camera has no tilt-features")
        tilt_speed = clamp(tilt_speed, -1.0, 1.0) # -100% - +100%
        tilt_speed = scale(tilt_speed, -1.0, 1.0, -100, 100)
        self.ptz.continuous_pantilt(0, tilt_speed);

    def set_brightness(self, brightness: float):
        brightness = clamp(brightness)
        brightness = scale(brightness, to_min=1, to_max=9999)
        self.ptz.set_brightness(brightness)


if __name__ == "__main__":
    # camera = CameraControl()
    # camera.start()
    # camera.stop()
    # Initialize the API caller with the base URL
    import logging
    logging.basicConfig(level=logging.INFO)

    vapix_api = VapixAPI('10.1.3.70', 'root', 'root', 80)

    vapix_api.ptz.continuous_pantilt(pan_speed=20, tilt_speed=0)
    time.sleep(1)
    vapix_api.ptz.continuous_pantilt(pan_speed=0, tilt_speed=0)
    time.sleep(1)
    sys.exit()

    # vapix_api = VapixAPI('10.1.3.70', 'root', 'root', 80)
    if vapix_api.optics.is_available():
        print(vapix_api.optics.get_optics())
        print()
        print(vapix_api.optics.get_capabilities())
        vapix_api.optics.set_magnification(optics_id=0, magnification=0.0)
        time.sleep(5)
        vapix_api.optics.set_magnification(optics_id=0, magnification=2.0)
        time.sleep(5)
        vapix_api.optics.set_magnification(optics_id=0, magnification=1.5)
        time.sleep(5)
        vapix_api.optics.set_magnification(optics_id=0, magnification=1.0)
        time.sleep(5)

    print()
    if vapix_api.ptz.is_available():
        print(vapix_api.ptz.get_current_position())

    '''
    position:
    pan=104.54
    tilt=-6.03
    zoom=1
    focus=1852
    brightness=5000
    autofocus=on
    autoiris=on
    '''
    
    vapix_api.ptz.continuous_move(pan_speed=0, tilt_speed=0, zoom_speed=1)
    time.sleep(5)
    vapix_api.ptz.continuous_move(pan_speed=0, tilt_speed=0, zoom_speed=0)

    print(vapix_api.ptz.get_current_position())

    vapix_api.ptz.continuous_move(pan_speed=0, tilt_speed=0, zoom_speed=-1)
    time.sleep(5)
    vapix_api.ptz.continuous_move(pan_speed=0, tilt_speed=0, zoom_speed=0)

    print(vapix_api.ptz.get_current_position())
