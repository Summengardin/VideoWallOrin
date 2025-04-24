

class CameraControl:
    def __init__(self):
        print("Camera Control Initialized")

    def start(self):
        print("Camera Control Started")

    def stop(self):
        print("Camera Control Stopped")

    def set_exposure(self, exposure_value: float):
        """
        Set the camera's exposure time.
        
        Args:
            exposure_value (float): Desired exposure value (in microseconds or the unit used by the camera).
        """
        print(f"Setting exposure to {exposure_value} microseconds")



if __name__ == "__main__":
    camera = CameraControl()
    camera.start()
    camera.stop()

