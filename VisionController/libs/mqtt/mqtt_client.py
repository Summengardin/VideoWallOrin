import paho.mqtt.client as mqtt
import time
import threading

import logging
logger = logging.getLogger(__name__)


class MQTTClient:
    def __init__(self, broker, port, topics, userdata=None):
        self.broker = broker
        self.port = port
        self.topics = topics
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, userdata=userdata)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.running = False
        self.connected = False

        self.connection_thread = None
        self.connection_timeout = threading.Event()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info("Connected to MQTT Broker!")
            self.connected = True
            for topic in self.topics:
                client.subscribe(topic)
                logger.debug(f"Subscribed to {topic}")
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
        # Try to reconnect if not disconnected intentionally
        self._reconnect()

    def _reconnect(self):

        while self.running:
            try:
                self.client.reconnect()
                break
            except ConnectionRefusedError:
                if self.running:
                    logger.error(f"Connection to MQTT broker ({self.broker}:{self.port}) refused. Trying again.")
            except TimeoutError:
                if self.running:
                    logger.error(f"Reconnection to MQTT broker ({self.broker}:{self.port}) timed out. Trying again.")

            self.connection_timeout.wait(5)


    def start(self):
        self.running = True
        self.client.connect_async(self.broker, self.port)
        self.client.loop_start()

        while self.running and not self.connected:
            self.connection_timeout.wait(5)  
            if self.connected:
                break
            if self.running:        
                logger.error("Connection to MQTT broker timed out. Trying again.")


    def stop(self):
        self.running = False
        logger.info("Waiting for MQTT client to shutdown")
        self.connection_timeout.set()
        self.client.loop_stop()
        self.client.disconnect()



# Usage example
if __name__ == "__main__":

    client = MQTTClient("localhost", 1883, ["VisionControllers/VisionController0/Stop"])
    client.start()


    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    client.stop()