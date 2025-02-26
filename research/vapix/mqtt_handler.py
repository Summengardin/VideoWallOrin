from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, Callable, Optional, Union, TypeVar, Protocol
import logging
import re
from abc import ABC

logger = logging.getLogger(__name__)

T = TypeVar('T', int, float)

class Controller(Protocol):
    def set_zoom(self, value: float) -> bool: ...
    def set_exposure(self, value: float) -> bool: ...
    def set_gain(self, value: float) -> bool: ...
    def set_focus(self, value: float, auto: bool = False) -> bool: ...

@dataclass
class Camera:
    id: str
    ip: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    type: Optional[str] = None
    controller: Optional[Controller] = None
    has_zoom: bool = False

    def set_controller(self, controller: Controller) -> None:
        self.controller = controller
        self.has_zoom = hasattr(controller, 'set_zoom')

@dataclass
class CameraFeature:
    name: str
    value_type: type
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    requires_controller_type: Optional[type] = None

    def validate_value(self, value: Any) -> Any:
        if self.value_type == bool:
            return bool(int(value))
        try:
            val = self.value_type(value)
            if self.min_value is not None:
                val = max(self.min_value, val)
            if self.max_value is not None:
                val = min(self.max_value, val)
            return val
        except ValueError as e:
            raise ValueError(f"Invalid {self.name} value: {value}") from e

class MQTTCommandHandler:
    def __init__(self, pipeline_manager, cameras: Dict[str, Camera], executor):
        """Initialize MQTT command handler.
        
        Args:
            pipeline_manager: Pipeline manager instance
            cameras: Dictionary of camera instances
            executor: Executor for running async tasks
        """
        self.pipeline_manager = pipeline_manager
        self.cameras = cameras
        self.executor = executor
        self._init_command_registries()
        self._init_feature_definitions()

    def _init_command_registries(self):
        """Initialize command registries with their handlers"""
        self.vision_commands = {
            'Fullscreen': lambda p: self.pipeline_manager._set_fullscreen(int(p)),
            'Width': lambda p: self._update_pipeline_config('Width', p),
            'Height': lambda p: self._update_pipeline_config('Height', p),
            'TilerRows': lambda p: self._update_pipeline_config('TilerRows', p),
            'TilerColumns': lambda p: self._update_pipeline_config('TilerColumns', p),
        }
        
        self.camera_commands = {
            'IP': lambda cam, p: setattr(cam, 'ip', p),
            'Type': self._handle_camera_type,
            'Name': lambda cam, p: setattr(cam, 'name', p),
            'Width': lambda cam, p: setattr(cam, 'width', self._validate_numeric(p, int)),
            'Height': lambda cam, p: setattr(cam, 'height', self._validate_numeric(p, int)),
            'Format': lambda cam, p: setattr(cam, 'format', p),
            'Framerate': lambda cam, p: setattr(cam, 'framerate', self._validate_numeric(p, float)),
            'Username': lambda cam, p: setattr(cam, 'username', p),
            'Password': lambda cam, p: setattr(cam, 'password', p)
        }

    def _init_feature_definitions(self):
        """Initialize camera feature definitions"""
        self.features = {
            'Zoom': CameraFeature('zoom', float, 1.0, 9999.0),
            'Exposure': CameraFeature('exposure_time', float),
            'ExposureAuto': CameraFeature('exposure_auto', bool),
            'Gain': CameraFeature('gain', float, 0.0, 100.0),
            'Focus': CameraFeature('focus', float, requires_controller_type=VapixController),
            'FocusAuto': CameraFeature('focus_auto', bool, requires_controller_type=VapixController)
        }

        self.source_commands = {
            'Source': self._handle_source_command,
            'Enable': self._handle_enable_command,
            **{name: lambda sid, p, n=name: self._handle_feature(sid, n, p) 
               for name in self.features}
        }

    def handle_message(self, topic: str, payload: str) -> None:
        """Handle incoming MQTT message.
        
        Args:
            topic: MQTT topic
            payload: Message payload
        """
        try:
            topic_parts = topic.split('/')
            base_topic = topic_parts[0]

            handlers = {
                'VisionControllers': self._handle_vision_message,
                'Cameras': self._handle_camera_message
            }

            handler = handlers.get(base_topic)
            if handler:
                handler(topic_parts[1:], payload)
            else:
                logger.warning(f"Unknown topic base: {base_topic}")
        except Exception as e:
            logger.error(f"Error handling message {topic}: {e}", exc_info=True)

    def _handle_vision_message(self, topic_parts: list, payload: str) -> None:
        command = topic_parts[0]
        
        if command.startswith('Tile'):
            try:
                source_id = int(re.findall(r'\d+', command)[0]) - 1
                subcommand = topic_parts[1]
                handler = self.source_commands.get(subcommand)
                if handler:
                    handler(source_id, payload)
            except (ValueError, IndexError) as e:
                logger.error(f"Invalid tile command: {command}", exc_info=True)
            return

        handler = self.vision_commands.get(command)
        if handler:
            try:
                handler(payload)
            except Exception as e:
                logger.error(f"Error handling vision command {command}: {e}", exc_info=True)

    def _handle_camera_message(self, topic_parts: list, payload: str) -> None:
        cam_id = topic_parts[0]
        command = topic_parts[1]
        
        try:
            camera = self.cameras.get(cam_id)
            if not camera:
                camera = Camera(id=cam_id)
                self.cameras[cam_id] = camera
                
            handler = self.camera_commands.get(command)
            if handler:
                handler(camera, payload)
        except Exception as e:
            logger.error(f"Error handling camera command {command}: {e}", exc_info=True)

    def _handle_feature(self, source_id: int, feature_name: str, payload: str) -> None:
        try:
            source = self.pipeline_manager.sources[source_id]
            if not source.camera.controller:
                return

            feature = self.features[feature_name]
            
            if (feature.requires_controller_type and 
                not isinstance(source.camera.controller, feature.requires_controller_type)):
                return

            value = feature.validate_value(payload)
            method_name = f"set_{feature.name}"
            
            if not hasattr(source.camera.controller, method_name):
                logger.error(f"Controller missing method: {method_name}")
                return

            success = self._run_with_timeout(
                getattr(source.camera.controller, method_name),
                args=(value,) if feature.value_type != bool else (),
                kwargs={} if feature.value_type != bool else {'auto': value}
            )

            if success:
                display_value = 'Auto' if feature.value_type == bool and value else value
                self._update_osd_text(source_id, f"{feature_name}: {display_value}")
        except Exception as e:
            logger.error(f"Error handling feature {feature_name}: {e}", exc_info=True)

    def _update_pipeline_config(self, command: str, payload: str) -> None:
        try:
            setattr(self.pipeline_manager, command.lower(), int(payload))
        except (ValueError, AttributeError) as e:
            logger.error(f"Error updating pipeline config {command}: {e}")

    def _run_with_timeout(self, func: Callable, args: tuple = (), 
                         kwargs: dict = None, timeout: int = 5) -> bool:
        if kwargs is None:
            kwargs = {}
            
        future = self.executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except Exception as e:
            logger.error(f"Function {func.__name__} error: {e}", exc_info=True)
            return False

    def _update_osd_text(self, source_id: int, text: str) -> None:
        try:
            self.pipeline_manager.osd_manager[source_id].upsert_text(
                text, "feature", 940, 980, 'c', 36,
                (1.0, 1.0, 1.0, 1.0), (0, 0, 0, 0.6), 2
            )
        except Exception as e:
            logger.error(f"Error updating OSD text: {e}", exc_info=True)