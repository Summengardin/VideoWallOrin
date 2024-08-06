import paho.mqtt.client as mqtt
import threading
import time

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s:  %(message)s')
logger = logging.getLogger(__name__)


class MQTTClient:
    def __init__(self, broker, port, topics, userdata=None, client_id=None, keepalive=60):
        self.broker = broker
        self.port = port
        self.client_id = client_id
        self.keepalive = keepalive
        self.topics = topics
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, userdata=userdata)
        
        # Assign event callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        self.message_handler = None
        self.connected = False
        self.running = False


        self.connection_thread = None

    def on_connect(self, client, userdata, flags, reason_code, properties):
        """Callback for when the client receives a CONNACK response from the server."""
        if reason_code == 0:
            logger.info("Connected to broker")
            self.connected = True
            # Subscribe to topics if any
            for topic in self.topics:
                client.subscribe(topic)
        else:
            print(f"Failed to connect, return code {reason_code}")

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        """Callback for when the client disconnects from the server."""
        print("Disconnected from broker")
        self.connected = False
        # Try to reconnect if not disconnected intentionally
        while self.running and not self.connected:
            try:
                print("Attempting to reconnect...")
                client.reconnect()
            except Exception as e:
                print(f"Reconnection failed: {e}")
                time.sleep(5)

    def on_message(self, client, userdata, message):
        """Callback for when a PUBLISH message is received from the server."""
        print(f"Received `{message.payload.decode()}` from `{message.topic}` topic")
        if self.message_handler:
            self.message_handler(message)


    def start(self):
        """Starts the MQTT client and connects to the broker."""
        self.running = True
        self.connection_thread = threading.Thread(target=self._connect_loop)
        self.connection_thread.start()

    def _connect_loop(self):
        """Attempts to connect to the broker and starts the loop."""
        while self.running and not self.connected:
            try:
                logger.info("Trying to connect to broker...")
                self.client.connect(self.broker, self.port, self.keepalive)
                self.client.loop_start()
            except Exception as e:
                print(f"Connection attempt failed: {e}")
                time.sleep(5)

    def stop(self):
        """Stops the MQTT client gracefully."""
        self.running = False
        if self.connection_thread:
            self.connection_thread.join()
        if self.connected:
            self.client.loop_stop()
            self.client.disconnect()

    def publish(self, topic, payload, qos=0):
        """Publish a message to a specified topic."""
        if self.connected:
            self.client.publish(topic, payload, qos)
        else:
            print("Cannot publish, client is not connected.")

if __name__ == "__main__":
    # Example usage
    mqtt_client = MQTTClient(broker="mqtt.eclipseprojects.io", port=1883, topics=["test/topic"])
    mqtt_client.start()

    try:
        while True:
            time.sleep(1)
            # Example publish message
            mqtt_client.publish("test/topic", "Hello MQTT")
    except KeyboardInterrupt:
        print("Stopping client")
        mqtt_client.stop()
