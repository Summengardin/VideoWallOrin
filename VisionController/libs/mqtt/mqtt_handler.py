import json
import queue
from typing import Dict, Any
from threading import Event

class MQTTHandler:
    def __init__(self):
        self.cameras: Dict[str, Dict[str, Any]] = {}
        self.vision_controllers: Dict[str, Dict[str, Any]] = {}
        
        self.is_running = False
        self.message_queue = queue.Queue()


    def run(self):
        while not self.is_running:
            try:
                topic, payload = self.message_queue.get(timeout=1.0)
                self._process_message(topic, payload)
            except queue.Empty:
                continue

    def handle_message(self, topic: str, payload: str) -> None:
        """Add message to queue for processing"""
        self.message_queue.put((topic, payload))
        

    def _process_message(self, topic: str, payload: str) -> None:
        """Process individual MQTT message"""
        topic_parts = topic.split('/')
        
        if topic_parts[0] == 'Cameras':
            camera_id = topic_parts[1]
            parameter = topic_parts[2]
            
            if camera_id not in self.cameras:
                self.cameras[camera_id] = {}
                
            self.cameras[camera_id][parameter] = self._parse_payload(payload)

        elif topic_parts[0] == 'VisionControllers':
            controller_id = topic_parts[1]
            
            if controller_id not in self.vision_controllers:
                self.vision_controllers[controller_id] = {
                    'tiles': {}
                }
            
            if len(topic_parts) > 3 and topic_parts[2].startswith('Tile'):
                tile_id = topic_parts[2]
                parameter = topic_parts[3]
                
                if tile_id not in self.vision_controllers[controller_id]['tiles']:
                    self.vision_controllers[controller_id]['tiles'][tile_id] = {}
                    
                self.vision_controllers[controller_id]['tiles'][tile_id][parameter] = self._parse_payload(payload)
            else:
                parameter = topic_parts[2]
                self.vision_controllers[controller_id][parameter] = self._parse_payload(payload)

    def _parse_payload(self, payload: str) -> Any:
        """Parse payload string into appropriate type"""
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            try:
                return float(payload)
            except ValueError:
                try:
                    return int(payload)
                except ValueError:
                    return payload

    def get_camera_property(self, camera_id: str, property_name: str) -> Any:
        """Get specific camera property"""
        return self.cameras.get(camera_id, {}).get(property_name)

    def get_controller_property(self, controller_id: str, property_name: str) -> Any:
        """Get specific controller property"""
        return self.vision_controllers.get(controller_id, {}).get(property_name)

    def get_tile_property(self, controller_id: str, tile_id: str, property_name: str) -> Any:
        """Get specific tile property"""
        return self.vision_controllers.get(controller_id, {}).get('tiles', {}).get(tile_id, {}).get(property_name)