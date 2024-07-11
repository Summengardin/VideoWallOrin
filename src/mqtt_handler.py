import logging
import multiprocessing
from queue import Empty

from libs.mqtt.mqtt_client import MQTTClient
from libs.gst.pipeline import handle_mqtt_message

logger = logging.getLogger(__name__)

def mqtt_handler(queue: multiprocessing.Queue, stop_event: multiprocessing.Event):
    while not stop_event.is_set():
        try:
            topic, payload = queue.get(timeout=1)
            if topic is None:
                logger.debug("MQTT shutdown queue signaled")
                stop_event.set()
                break
            handle_mqtt_message(topic, payload)
        except Empty:
            continue
        except Exception as e:
            logger.error(f"Error handling MQTT message: {e}")
            continue

def mqtt_on_message_callback(client, userdata, message):
    payload = message.payload.decode('utf-8')
    userdata['queue'].put((message.topic, payload))
    logger.debug(f"Queued message on topic {message.topic}: {payload}")

def run_mqtt(stop_event: multiprocessing.Event, queue: multiprocessing.Queue, config):
    mqtt_client = MQTTClient(config['broker'], config['port'], build_mqtt_topics(config), userdata={'queue': queue})
    mqtt_client.set_on_message_callback(mqtt_on_message_callback)
    
    while not stop_event.is_set():
        try:
            mqtt_client.start()
            break
        except TimeoutError:
            if stop_event.is_set():
                logging.info("Connection to MQTT broker timed out. Exiting.")
                break
            else:
                logging.error("Connection to MQTT broker timed out. Trying again.")
        except KeyboardInterrupt:
            break

    stop_event.wait()
    mqtt_client.stop()
    logger.debug("MQTT client stopped")

def build_mqtt_topics(config):
    topics = []
    for camera in config['cameras']:
        for subtopic in config['camera_subtopics']:
            topics.append((camera + subtopic if isinstance(subtopic, str) else list(subtopic.keys())[0], 0 if isinstance(subtopic, str) else list(subtopic.values())[0]))
    for vision_controller in config['vision_controllers']:
        for subtopic in config['vision_controller_subtopics']:
            topics.append((vision_controller + subtopic if isinstance(subtopic, str) else list(subtopic.keys())[0], 0 if isinstance(subtopic, str) else list(subtopic.values())[0]))
    topics.append(('VisionControllers/VisionController0/Stop', 1))
    return topics
