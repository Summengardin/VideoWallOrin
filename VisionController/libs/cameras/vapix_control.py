import time
import logging

import sys
sys.path.append('/app/VisionController/libs')

from vapix_python.VapixAPI import VapixAPI
from utils import clamp


logger = logging.getLogger(__name__)

class CameraControl:
    def __init__(self, camera, username='root', password='root', port=80):
        logger.debug(f"Initializing CameraControl for {camera.ip}")
        self.vapix_control = VapixAPI(camera.ip, username, password, port)
        self.ptz = self.vapix_control.ptz
        self.optics = self.vapix_control.optics
        # Its only either for mechanical zoom. If mechanical PTZ is available, then optics is not available.
        self.use_optics = self.optics.is_available()

    def set_zoom(self, zoom_level: float):
        zoom_level = clamp(zoom_level) # 0.0 to 1.0
        if self.use_optics:
            
            self.optics.set_magnification(optics_id=0, magnification=zoom_level)
        else:
            self.ptz.continuous_move(pan_speed=0, tilt_speed=0, zoom_speed=zoom_level)




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
