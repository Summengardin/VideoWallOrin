import argparse
import multiprocessing
import threading
import sys

sys.path.append('..')

from libs.config.config import Config
from libs.mqtt.mqtt_handler import MqttHandler
from libs.gst.pipeline import GStreamerPipeline

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', '-c', type=str, default='/home/seaonics/Dev/VideoWallOrin/libs/config/config.yml')
    args = parser.parse_args()

    config_file = args.config
    config = Config(config_file)

    stop_event = multiprocessing.Event()
    message_queue = multiprocessing.Queue()

    mqtt_handler = MqttHandler(stop_event, message_queue, config.mqtt_config)
    mqtt_process = multiprocessing.Process(target=mqtt_handler.run)
    mqtt_process.start()

    pipeline = GStreamerPipeline(config.pipeline_config)
    pipeline_thread = threading.Thread(target=pipeline.run)
    pipeline_thread.start()

    try:
        print("\nProgram is running\n")
        stop_event.wait()
    except KeyboardInterrupt:
        stop_event.set()

    message_queue.put(None)  # signal the queue to close

    if pipeline.loop:
        pipeline.loop.quit()
    
    pipeline_thread.join()
    mqtt_process.join()

if __name__ == "__main__":
    main()
