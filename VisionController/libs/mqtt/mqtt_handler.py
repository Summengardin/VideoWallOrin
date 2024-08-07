

import logging
logger = logging.getLogger(__name__)
import queue

from ..gst.pipeline_manager import PipelineManager
from ..mqtt.mqtt_client_ import MQTTClient
from ..types import SourceType, Source, Camera

class MQTTHandler:
    def __init__(self, config = None, command_queue: queue.Queue = None, pipeline_manager: PipelineManager = None):
        self.config = config
        self.command_queue = command_queue
        self.pipeline_manager = pipeline_manager
        
        self.mqtt_client = MQTTClient

        self.mqtt_client.set_on_message_callback(on_message)
        mqtt_thread = threading.Thread(target=mqtt_client.start)
        mqtt_thread.start() 
            
        
    def _build_topics(self, cameras, camera_subtopics, vision_controllers, vision_controller_subtopics):
        topics = []
        for camera in cameras:
            for subtopic in camera_subtopics:
                if type(subtopic) is dict:
                    topic = subtopic.keys()[0]
                    qos = subtopic.values()[0]
                    topics.append((camera + topic, qos))
                else:
                    topics.append((camera + subtopic, 0))

        for vision_controller in vision_controllers:
            for subtopic in vision_controller_subtopics:
                if isinstance(subtopic, dict):
                    topic = list(subtopic.keys())[0]
                    qos = subtopic[topic]
                    topics.append((vision_controller + topic, qos))
                else:
                    topics.append((vision_controller + subtopic, 0))

        return topics
