import importlib
import logging

logger = logging.getLogger(__name__)

class SourceManager:
    """
    Manages the loading, configuration, and control of camera sources and controls.
    
    This class decouples the GStreamer source (pipeline/bin) creation from camera control
    logic by dynamically loading provider-specific modules based on camera type.
    
    Attributes:
        camera_configs (list): A list of camera configuration objects.
        sources (dict): Maps camera identifiers (e.g., IP address) to their GStreamer source bins.
        controls (dict): Maps camera identifiers to their control interface objects.
        providers (dict): Maps camera types to provider module paths.
    """

    def __init__(self, camera_configs):
        """
        Initialize the SourceManager with a list of camera configurations.
        
        Args:
            camera_configs (list): List of camera configuration objects. Each camera config
                                   should have attributes like 'ip', 'width', 'height', 'format',
                                   'framerate', 'type', etc.
        """
        self.camera_configs = camera_configs
        self.sources = {}
        self.controls = {}
        self.providers = {}

    def register_provider(self, camera_type, source_module_path, control_module_path):
        """
        Register a camera provider for a specific camera type.
        
        This registers the module paths that will be dynamically imported later.
        
        Args:
            camera_type (str): The camera type identifier (e.g., "Aravis", "Basler").
            source_module_path (str): Python module path for the source bin creation function.
            control_module_path (str): Python module path for the camera control class.
        """
        self.providers[camera_type] = {
            "source": source_module_path,
            "control": control_module_path
        }
        logger.info("Registered provider for %s: source=%s, control=%s", 
                    camera_type, source_module_path, control_module_path)

    def load_camera(self, index, camera):
        """
        Load a single camera’s source bin and control interface.
        
        Uses the registered provider for the camera type to import the corresponding modules.
        
        Args:
            index (int): The index of the camera in the configuration list.
            camera (object): The camera configuration object.
            
        Returns:
            bool: True if the camera was loaded successfully, False otherwise.
        """
        camera_type = camera.type
        provider = self.providers.get(camera_type)
        if not provider:
            logger.error("Unsupported camera type: %s", camera_type)
            return False

        try:
            # Dynamically import the modules for source and control.
            source_module = importlib.import_module(provider["source"])
            control_module = importlib.import_module(provider["control"])
        except ImportError as e:
            logger.error("Error importing modules for camera type %s: %s", camera_type, e)
            return False

        try:
            # Create the GStreamer source bin.
            # The source module should expose a function 'create_source_bin'
            source_bin = source_module.create_source_bin(index, camera)
            # Create the camera control object.
            # The control module should provide a class (e.g., 'CameraControl')
            control_obj = control_module.CameraControl(camera)
        except Exception as e:
            logger.error("Failed to create components for camera %s (%s): %s", camera.ip, camera_type, e)
            return False

        # Save the created objects in dictionaries keyed by a unique camera identifier.
        self.sources[camera.ip] = source_bin
        self.controls[camera.ip] = control_obj

        logger.info("Loaded camera %s of type %s", camera.ip, camera_type)
        return True

    def load_all_cameras(self):
        """
        Iterates over the camera configuration and loads all cameras.
        """
        for index, camera in enumerate(self.camera_configs):
            success = self.load_camera(index, camera)
            if not success:
                logger.warning("Skipping camera %s due to previous errors.", camera.ip)

    def get_source_bin(self, camera_id):
        """
        Retrieve the source bin (GStreamer bin) for a given camera.
        
        Args:
            camera_id (str): The unique identifier for the camera (e.g., its IP address).
        
        Returns:
            object: The GStreamer bin associated with the camera, or None if not found.
        """
        return self.sources.get(camera_id)

    def get_control(self, camera_id):
        """
        Retrieve the control interface for a given camera.
        
        Args:
            camera_id (str): The unique identifier for the camera.
        
        Returns:
            object: The control interface object, or None if not found.
        """
        return self.controls.get(camera_id)

    def start_all(self):
        """
        Starts the control interface for all loaded cameras.
        
        Assumes each control interface implements a 'start' method.
        """
        for camera_id, control in self.controls.items():
            try:
                control.start()
                logger.info("Started control for camera %s", camera_id)
            except Exception as e:
                logger.error("Failed to start control for camera %s: %s", camera_id, e)

    def stop_all(self):
        """
        Stops the control interface for all loaded cameras.
        
        Assumes each control interface implements a 'stop' method.
        """
        for camera_id, control in self.controls.items():
            try:
                control.stop()
                logger.info("Stopped control for camera %s", camera_id)
            except Exception as e:
                logger.error("Failed to stop control for camera %s: %s", camera_id, e)

    def update_camera_setting(self, camera_id, setting, value):
        """
        Updates a specific camera setting using its control interface.
        
        The control interface is expected to have methods like set_exposure(), set_gain(), etc.
        The method name is dynamically constructed.
        
        Args:
            camera_id (str): The unique identifier for the camera.
            setting (str): The setting name (e.g., "exposure", "gain").
            value: The new value to be set.
        """
        control = self.get_control(camera_id)
        if control is None:
            logger.error("No control found for camera %s", camera_id)
            return

        # Construct the method name (e.g., "set_exposure")
        method_name = f"set_{setting}"
        try:
            method = getattr(control, method_name)
            method(value)
            logger.info("Updated setting %s for camera %s to %s", setting, camera_id, value)
        except AttributeError:
            logger.error("Control for camera %s does not support setting '%s'", camera_id, setting)
        except Exception as e:
            logger.error("Error updating setting %s for camera %s: %s", setting, camera_id, e)

    def get_camera_status(self, camera_id):
        """
        Retrieve a status summary from the camera's control interface.
        
        This might include details like current exposure, gain, or connection status.
        The control interface should implement a get_status() method that returns a dict.
        
        Args:
            camera_id (str): The unique identifier for the camera.
        
        Returns:
            dict: A dictionary containing status information or an empty dict if not available.
        """
        control = self.get_control(camera_id)
        if control and hasattr(control, "get_status"):
            try:
                return control.get_status()
            except Exception as e:
                logger.error("Error retrieving status for camera %s: %s", camera_id, e)
        return {}



# Example usage:
if __name__ == "__main__":
    # Imagine a list of camera configuration objects is defined somewhere.
    # Each object must have at least: ip, type, width, height, format, framerate, etc.
    camera_configs = [
        # For example, these could be instances of a CameraConfig class.
        # Here we use a simple dummy object for illustration.
        type("CameraConfig", (object,), {
            "ip": "10.1.3.81",
            "uri": "rtsp://root:root@10.1.3.81/axis-media/media.amp?streamprofile=stream-1",
            "type": "Axis",
            "width": 1920,
            "height": 1080,
            "format": "H265",
            "framerate": 60.0,
            "exposure_time_auto": 0,
            "exposure_time": 5000,
            "gain_auto": 0,
            "gain": 1.0
        })(),
        # Add more camera configurations as needed.
    ]

    # Create the manager and register providers.
    manager = SourceManager(camera_configs)
    # manager.register_provider("Aravis", "cameras.aravis_source_bin", "cameras.aravis_control")
    manager.register_provider("Axis", "cameras.uri_source_bin", "cameras.vapix_control")
    # If there are other providers:
    # manager.register_provider("Basler", "cameras.basler_source_bin", "cameras.basler_control")


    # Load cameras.
    manager.load_all_cameras()

    # Optionally, start all controls.
    manager.start_all()

    # Update a setting.
    manager.update_camera_setting("10.1.3.81", "exposure", 6000)

    # Retrieve a source bin or status.
    source_bin = manager.get_source_bin("10.1.3.81")
    status = manager.get_camera_status("10.1.3.81")
    logger.info("Camera status: %s", status)

    # When done, stop all cameras.
    manager.stop_all()
