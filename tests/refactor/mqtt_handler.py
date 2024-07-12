import logging
import multiprocessing
import time


class MqttHandler:
    def __init__(self, message_queue: multiprocessing.Queue):
        self.message_queue = message_queue
        self.pipeline = self.initialize_pipeline()

    def run(self):
        logging.info("MQTT Handler started")
        while True:
            try:
                message = self.message_queue.get(timeout=1)
                if message is None:     # Signals the queue to close
                    break
                topic, payload = message
                self.handle_message(topic, payload)

            except multiprocessing.queues.Empty:
                continue

    def handle_message(self, topic, message):
        logging.info(f"Message received on topic {topic}: {message}")


        if topic == "add_source":
            self.add_source(message)
        elif topic == "remove_source":
            self.remove_source(message)
        # Add more topic handlers as needed



        else:
            logging.warning(f"No handler for topic {topic}")


    def add_source(self, source):
        # Implement logic to add a source to the GStreamer pipeline
        logging.info(f"Adding source: {source}")
        # Example GStreamer manipulation code
        # self.pipeline.add_source(source)


    def remove_source(self, source):
        # Implement logic to remove a source from the GStreamer pipeline
        logging.info(f"Removing source: {source}")
        # Example GStreamer manipulation code
        # self.pipeline.remove_source(source)

    def initialize_pipeline(self):
        # Initialize GStreamer pipeline
        logging.info("Initializing GStreamer pipeline")
        # Example GStreamer pipeline initialization code
        pipeline = "GStreamer Pipeline Object"  # Replace with actual GStreamer pipeline object
        return pipeline



# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    message_queue = multiprocessing.Queue()

    # Example of putting messages into the queue
    # This should be done by the separate process running the MQTT client
    def simulate_mqtt_messages(queue):
        topics = ["add_source", "remove_source"]
        messages = ["source1", "source2"]
        for topic, message in zip(topics, messages):
            queue.put((topic, message))
            time.sleep(2)

    mqtt_process = multiprocessing.Process(target=simulate_mqtt_messages, args=(message_queue,))
    mqtt_process.start()

    mqtt_handler = MqttHandler(message_queue)
    try:
        mqtt_handler.run()
    except KeyboardInterrupt:
        logging.info("Stopping MQTT Handler")
        mqtt_process.terminate()
