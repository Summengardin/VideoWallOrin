import time
import logging
import json
import threading

import sys
sys.path.append('/app/VisionController/libs')

from vapix_python.VapixAPI import VapixAPI
from utils import clamp, scale
from VisionController.libs.cameras.base_camera_control import CameraControl

logger = logging.getLogger(__name__)

class VapixControl(CameraControl):
    def __init__(self, camera, username='root', password='root', port=80):
        logger.debug(f"Initializing CameraControl for {camera.ip}")
        try:
            self.vapix_control = VapixAPI(camera.ip, username, password, port)
        except Exception as e:
            logger.error(f"Failed to initialize VapixAPI for {camera.ip}: {e}")
            return 
        self.ptz = self.vapix_control.ptz
        self.optics = self.vapix_control.optics
        # self.imaging = self.vapix_control.imaging
        
        ''' VAPIX CAMERA CONTROL INTERNALS '''
        # If mechanical PTZ is available, then optics is not available.
        self._use_optics = self.optics.is_available()
        if self._use_optics:
            self._capabilities = self.optics.get_capabilities()  
            self._capabilities = json.loads(self._capabilities)
            self._max_magnification = self._capabilities['data']['optics'][0]['maxMagnification']
            self._current_magnification = 1.0 # 0 to 100
        

    def continuous_zoom(self, zoom_speed: float):
        zoom_speed = clamp(zoom_speed, -1.0, 1.0)

        if not self._use_optics:
            try:
                self.ptz.continuous_zoom(zoom_speed=zoom_speed * 100.0)  # [-100..100]
            except Exception:
                logger.exception("PTZ continuous_zoom failed")
            return
        # lazy init
        if not hasattr(self, "_mag_thread"):
            self._mag_speed = 0.0
            self._mag_rate = 2.0
            self._mag_stop = threading.Event()
            self._mag_thread = None
            self._mag_t = time.monotonic()

        self._mag_speed = zoom_speed

        # start worker if needed
        if zoom_speed != 0.0 and (self._mag_thread is None or not self._mag_thread.is_alive()):
            self._mag_stop.clear()

            def _worker():
                last = None
                while not self._mag_stop.is_set():
                    now = time.monotonic()
                    dt = now - self._mag_t
                    self._mag_t = now

                    if self._mag_speed == 0.0: 
                        time.sleep(0.05)
                        self._mag_stop.set() 
                        continue

                    self._current_magnification = max(1.0, min(
                        self._max_magnification,
                        self._current_magnification + self._mag_speed * self._mag_rate * dt))
                    
                    mag = self._current_magnification
                    if last is None or abs(mag - last) > 0.01:  # only set if changed
                        try: 
                            self.optics.set_magnification(0, mag)
                            last = mag
                        except Exception: 
                            logger.exception("set_magnification failed")
                    time.sleep(0.05)

            self._mag_thread = threading.Thread(target=_worker, daemon=True)
            self._mag_thread.start()

        # stop worker on zero
        if zoom_speed == 0.0 and self._mag_thread and self._mag_thread.is_alive():
            self._mag_stop.set()
            try: 
                self._mag_thread.join(0.2)
            except Exception: 
                pass
            self._mag_thread = None

        try: 
            self.optics.set_magnification(0, self._current_magnification)
        except Exception: 
            logger.exception("immediate set_magnification failed")


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
        self.ptz.continuous_pantilt(0, tilt_speed)

    def absolute_pan(self, pan_position):
        if not self.ptz.is_available:
            logger.debug("Camera has no pan-features")
        pan_position = clamp(pan_position, -180.0, 180.0) # -100% - +100%
        self.ptz.absolute_pan(pan=pan_position)

    def absolute_tilt(self, tilt_position):
        if not self.ptz.is_available:
            logger.debug("Camera has no pan-features")
        tilt_position = clamp(tilt_position, -180.0, 180.0) # -100% - +100%
        self.ptz.absolute_tilt(tilt=tilt_position)

    def absolute_zoom(self, zoom):
        if not self.ptz.is_available:
            logger.debug("Camera has no pan-features")
        zoom = clamp(zoom, 1, 9999) # -100% - +100%
        self.ptz.absolute_zoom(zoom=zoom)

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
