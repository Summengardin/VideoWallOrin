import paho.mqtt.client as mqtt
import time

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s:  %(message)s')
logger = logging.getLogger(__name__)

class MQTTClient:
    def __init__(self, broker, port, topics, userdata=None):
        self.broker = broker
        self.port = port
        self.topics = topics
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, userdata=userdata)

        # Assign callback functions
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

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
        if reason_code != 0:
            logger.error("Unexpected disconnection. Trying to reconnect...")
            self.start()
        else:
            logger.info("Disconnected from MQTT Broker.")

    def start(self):
        while True:
            try:
                self.client.connect(self.broker, self.port, 60)
                break
            except OSError:
                logger.error("Failed to connect to MQTT broker. Retrying in 5 seconds...")
                time.sleep(5)
                continue
            except TimeoutError:
                logger.error("Connection to MQTT broker timed out. Retrying in 5 seconds...")
                time.sleep(5)
                continue

        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()



# Usage example
if __name__ == "__main__":
    import signal
    from multiprocessing import Process, Event
    import yaml

    def parse_config(config_file):
        with open(config_file, 'r') as file:
            config = yaml.safe_load(file)
            return config

    def run_mqtt_client(stop_event):
        global mqtt_client

        config = parse_config('mqtt_config.yml')
        broker = config['broker']
        port = config['port']
        root_topic = config['cameras']
        subtopics = config['camera_subtopics']
        
        topics = [ (root_topic + subtopic, 0) for subtopic in subtopics ]

        mqtt_client = MQTTClient(broker, port, topics)
        mqtt_client.start()


        stop_event.wait()

        mqtt_client.stop()


    def stop(signum, frame):
        print("Stopping MQTT Client...")
        stop_event.set()

    # Create a stop event
    stop_event = Event()

    # Create a separate process for the MQTT client
    process = Process(target=run_mqtt_client, args=(stop_event,))
    process.start()

    # Setup signal handling to stop the process gracefully
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        process.join()
    except KeyboardInterrupt:
        print("Stopping the process...")
        stop_event.set()
        process.join()
        print("Process stopped")
