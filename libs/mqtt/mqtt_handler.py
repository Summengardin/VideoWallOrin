import multiprocessing
from queue import Empty
import logging
from libs.mqtt.mqtt_client import MQTTClient
from libs.config.config import Config

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s:  %(message)s')
logger = logging.getLogger(__name__)

class MqttHandler:
    def __init__(self, stop_event, queue, config: Config):
        self.stop_event = stop_event
        self.queue = queue

        self.update_config(config)


    def on_message_callback(self, client, userdata, message):
        payload = message.payload.decode('utf-8')
        userdata['queue'].put((message.topic, payload))
        logger.debug(f"Queued message on topic {message.topic}: {payload}")

    def topics_from_config(self, config):
        topics = []
        for camera in config['cameras']:
            for subtopic in config['camera_subtopics']:
                if type(subtopic) is dict:
                    topic = subtopic.keys()[0]
                    qos = subtopic.values()[0]
                    topics.append((camera + topic, qos))
                else:
                    topics.append((camera + subtopic, 0))
        
        for vision_controller in config['vision_controllers']:
            for subtopic in config['vision_controller_subtopics']:
                if type(subtopic) is dict:
                    topic = list(subtopic)[0]
                    qos = subtopic[topic]
                    topics.append((vision_controller + topic, qos))
                else:
                    topics.append((vision_controller + subtopic, 0))

        return topics

    def update_config(self, config: Config):
        self.config = config
        self.broker = config['broker']
        self.port = config['port']
        self.topics = self.topics_from_config(config)

    def run(self):
      
        mqtt_client = MQTTClient(self.broker, self.port, self.topics, userdata={'queue': self.queue})
        mqtt_client.set_on_message_callback(self.on_message_callback)

        while not self.stop_event.is_set():
            try:
                mqtt_client.start()
                break
            except TimeoutError:
                logger.error("Connection to MQTT broker timed out. Trying again.")
            except KeyboardInterrupt:
                break

        self.stop_event.wait()
        mqtt_client.stop()
        logger.debug("MQTT client stopped")
