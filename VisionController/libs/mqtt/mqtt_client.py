import paho.mqtt.client as mqtt
import threading
import time

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s:  %(message)s')
logger = logging.getLogger(__name__)


class MQTTClient(mqtt.Client):
    def __init__(self, broker, port, topics, stop_event, userdata=None):
        self.broker = broker
        self.port = port
        self.topics = topics
        self.running = False
        self.stop_event = stop_event
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, userdata=userdata)

        # Assign callback functions
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.connected = False

        self.connection_thread = None

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info("Connected to MQTT Broker!")
            for topic in self.topics:
                client.subscribe(topic)
                logger.debug(f"Subscribed to {topic[0]}")  
        else:
            logger.error(f"Failed to connect, return code {reason_code}")

    def on_message(self, client, userdata, msg):
        print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")

    def set_on_message_callback(self, callback):
        self.client.on_message = callback

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        """Callback for when the client disconnects from the server."""
        logger.info("Disconnected from broker")
        self.connected = False
        