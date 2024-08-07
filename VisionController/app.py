import threading
import time
import queue

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GLib

import logging
logger = logging.getLogger(__name__)


from .libs.gst.pipeline_manager import PipelineManager
from .libs.types import SourceType, Source, Camera
from .libs.mqtt.mqtt_client_ import MQTTClient

Gst.init(None)

seq_step = 0
add_remove = 1

Cameras = [Camera(ip="10.1.3.74", type="Basler", width=1920, height=1080, format="BayerRG8", framerate=60), Camera(ip="10.1.3.79", type="TheImagingSource", width=1920, height=1080, format="BayerRG8", framerate=54)]


pipeline_manager = PipelineManager(streammux_config_file="./config/streammux_config.txt")
mqtt_client = MQTTClient('192.168.181.203', 1883, ['VisionControllers/VisionController0/Width'])
command_queue = queue.Queue()

def source_sequencer():
    global seq_step, add_remove
    if seq_step >= len(Cameras):
        seq_step = len(Cameras) - 1
        add_remove = -1

    if seq_step < 0:
        seq_step = 0
        add_remove = 1

    index = seq_step
    seq_step += add_remove

    if add_remove == 1:
        pipeline_manager.sources[index].enabled = True
        pipeline_manager.add_source(index, Cameras[index])
    else:
        pipeline_manager.sources[index].enabled = False
        pipeline_manager.remove_source(index)
        pipeline_manager.add_source(index)


def mqtt_handler():
    while True:
        msg = command_queue.get()
        if msg is None:
            break


        




        topic, payload = msg
        logger.debug(f"Dequeued: {topic}  -  {payload}") 


def on_message(client, userdata, msg):
    payload = msg.payload.decode('utf-8')
    command_queue.put((msg.topic, payload))
    logger.debug(f"Queued:    {msg.topic}  -  {payload}")



def run():
    global pipeline_manager

    pipeline_thread = threading.Thread(target=pipeline_manager.start)
    pipeline_thread.start()


    mqtt_client.set_on_message_callback(on_message)
    mqtt_thread = threading.Thread(target=mqtt_client.start)
    mqtt_thread.start() 


    handler_thread = threading.Thread(target=mqtt_handler)
    handler_thread.start()
  



    try:
        while True:
            time.sleep(10)
            source_sequencer()        
    except KeyboardInterrupt:
        pass
    finally:
        command_queue.put(None)
        pipeline_manager.stop()

    mqtt_client.stop()

    handler_thread.join()
    mqtt_thread.join()
    pipeline_thread.join()

    print("Done")