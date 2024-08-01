import sys
import threading
import multiprocessing
import traceback
import time

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version("Gtk", "4.0")
from gi.repository import Gst, GLib

sys.path.append('..')
from libs.types import SourceType, Source, Camera, PipelineConfig
from libs.gst.source_bins import create_uridecodebin_source_bin, create_aravis_source_bin, create_placeholder_source_bin, create_videotestsrc_source_bin, create_camgrabber_source_bin
from libs.utils import index_dataclass, find_digits_in_string, parse_config
from libs.mqtt.mqtt_client import MQTTClient
from config.config import Config

from functools import partial
from dataclasses import dataclass
from queue import Empty

import logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s [%(levelname)s] %(name)s:  %(message)s')
logger = logging.getLogger(__name__)

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--config', '-c', type=str, default='/home/seaonics/Dev/VideoWallOrin/config/config.yml')

Gst.init(None)



# Constants (That can be modified with GUI)    

pipeline_config = PipelineConfig()
OUTPUT_WIDTH = 3840
OUTPUT_HEIGHT = 2160
TILER_ROWS = 2
TILER_COLS = 2
MAX_NUM_SOURCES = TILER_ROWS * TILER_COLS
SINK_ELEMENT = "nv3dsink"
# SINK_ELEMENT = "nvdrmvideosink"

THIS_CONTROLLER_ID = 0


# Global variables
g_num_sources = 0
g_sources = [Source(id=i, name=f"Source {i}") for i in range(MAX_NUM_SOURCES)]
g_cameras = [Camera() for i in range(10)]
pipeline = None
streammux = None
sink = None
nvvideoconvert = None
nvosd = None
tiler = None
pgie = None
loop = None
zoom_level = 0
enable_pipeline = False
pipeline_pause_because_last_source = False

g_cameras[9] = Camera(ip='test')
g_last_num_rendered_frames = 0

# ======================================================
#                   MQTT Related Functions
# ======================================================

def run_with_timeout(func, args=(), kwargs={}, timeout=5):
    """Run a function with a timeout in a separate thread."""
    result = [None]
    exception = [None]

    def wrapper():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            exception[0] = e

    thread = threading.Thread(target=wrapper)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        logger.error(f"Function {func.__name__} timed out")
        return False
    if exception[0]:
        raise exception[0]
    return True

def mqtt_handler(queue: multiprocessing.Queue, stop_event: multiprocessing.Event):
    while not stop_event.is_set():
        try:
            q = queue.get(timeout=1)
            if q is None:
                logger.debug("Mqtt shutdown queue signaled")
                stop_event.set()
                break 

            topic, payload = q
                  
        except ValueError:
            logger.error("ValueError. Probably closed.")
            continue
        except Empty:
            continue

        logger.debug(f"Dequeued message on topic: {topic}: {payload}")  

        topic_split = topic.split('/')
        root_topic = topic_split[0]

        if root_topic == 'VisionControllers':
            command = topic_split[2]
            global pipeline_config
            if command == 'Shutdown' and int(payload) > 0:
                logger.debug("Stop event set")
                stop_event.set()
            elif command == 'Width':
                global OUTPUT_WIDTH
                OUTPUT_WIDTH = int(payload)
                pipeline_config.width = int(payload)
                logger.debug(f"Output width: {OUTPUT_WIDTH}")
            elif command == 'Height':
                global OUTPUT_HEIGHT
                OUTPUT_HEIGHT = int(payload)
                pipeline_config.height = int(payload)
                logger.debug(f"Output height: {OUTPUT_HEIGHT}")
            elif command == 'TilerRows':
                global TILER_ROWS
                TILER_ROWS = int(payload)
                pipeline_config.rows = int(payload)
                logger.debug(f"Tiler rows: {TILER_ROWS}")
            elif command == 'TilerColumns': 
                global TILER_COLS
                TILER_COLS = int(payload)
                pipeline_config.cols = int(payload)
                logger.debug(f"Tiler cols: {TILER_COLS}")
            elif command == 'StartPipeline':
                if int(payload) > 0:
                    pipeline_config.enable_pipeline = True
                    logger.debug(f"Pipeline enabled: {pipeline_config.enable_pipeline}")
                    # print("\n=== MISSING IMPLEMENTATION TO START PIPELINE ===\n")
            elif command.startswith('Tile'):
                global g_sources
                index = find_digits_in_string(command)
                source_id = index - 1
                subcommand = topic_split[3]

                if index is not None:
                    if subcommand == 'Source':
                        g_sources[source_id].ip = payload
                        logger.debug(f"Source {source_id} IP: {payload}")

                    elif subcommand == 'Enable':
                        if int(payload) > 0:
                            try:
                                camera_id = index_dataclass(g_cameras, 'ip', g_sources[source_id].ip)
                            except ValueError:
                                logger.error(f"Could not find camera with IP {g_sources[source_id].ip}")
                                continue

                            try:
                                success = run_with_timeout(add_source, args=(source_id,), kwargs={'camera': g_cameras[camera_id]})
                                if not success:
                                    logger.error(f"Adding source {source_id} timed out")
                            except Exception as e:
                                logger.error(f"Could not add source {source_id}")
                                traceback.print_exc()
                        else:
                            try:
                                success = run_with_timeout(remove_source, args=(source_id,))
                                if not success:
                                    logger.error(f"Removing source {source_id} timed out")
                                success = run_with_timeout(add_source, args=(source_id,))
                                if not success:
                                    logger.error(f"Adding placeholder source {source_id} timed out")
                            except Exception as e:
                                logger.error(f"Could not stop releasing source {source_id}")
                                traceback.print_exc()
         
        elif root_topic == 'CamObjects':
            g_cameras
            index = find_digits_in_string(topic_split[1])
            command = topic_split[2]

            if command == 'IP':
                g_cameras[index].ip = payload
            elif command == 'Type':
                g_cameras[index].type = payload
            elif command == 'Width':
                g_cameras[index].width = int(payload)
            elif command == 'Height':
                g_cameras[index].height = int(payload)
            elif command == 'Format':
                g_cameras[index].format = payload
            elif command == 'Framerate':
                g_cameras[index].framerate = float(payload)
            elif command == 'Zoom':
                g_cameras[index].zoom = int(payload)
            elif command == 'Exposure':
                g_cameras[index].exposure_time = float(payload)
            elif command == 'Gain':
                g_cameras[index].gain = float(payload)

    logger.debug("Mqtt handler finished")
    

def mqtt_on_message_callback(client, userdata, message):
    payload = message.payload.decode('utf-8')

    userdata['queue'].put((message.topic, payload))
    logger.debug(f"Queued message on topic {message.topic}: {payload}")
        
    
def run_mqtt(stop_event: multiprocessing.Event, queue: multiprocessing.Queue, config):

    mqtt_config = config
    broker = mqtt_config['broker']
    port = mqtt_config['port']
    cameras = mqtt_config['cameras']
    camera_subtopics = mqtt_config['camera_subtopics']
    vision_controllers = mqtt_config['vision_controllers']
    vision_controller_subtopics = mqtt_config['vision_controller_subtopics']

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
            if type(subtopic) is dict:
                topic = list(subtopic)[0]
                qos = subtopic[topic]
                topics.append((vision_controller + topic, qos))
            else:
                topics.append((vision_controller + subtopic, 0))

    topics.append(('VisionControllers/VisionController0/Stop', 1))

    mqtt_client = MQTTClient(broker, port, topics, userdata={'queue': queue})
    mqtt_client.set_on_message_callback(mqtt_on_message_callback)
    
    while True:
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

    try:
        stop_event.wait()
    except KeyboardInterrupt:
        stop_event.set()

    mqtt_client.stop()

    logger.debug("MQTT client stopped")




# ======================================================
#               GStreamer Related Functions
# ======================================================


def update_tiler():
    global TILER_ROWS, TILER_COLS, MAX_NUM_SOURCES

    MAX_NUM_SOURCES = TILER_ROWS * TILER_COLS

    if len(g_sources) > MAX_NUM_SOURCES:
        for i in range(MAX_NUM_SOURCES, len(g_sources)):
            remove_source(source_id=i)

    for i in range(MAX_NUM_SOURCES):
        if i > len(g_sources):
            g_sources.append(Source(id=i, name=f"Source {i}"))


def add_source(source_id: int = None, camera: Camera = None):
    
    logger.debug(f"Add Source: source_id = {source_id}, camera = {camera}")
    global g_sources, g_num_sources, pipeline, streammux, MAX_NUM_SOURCES
    global pipeline_pause_because_last_source

    if pipeline is None or streammux is None:
        return False

    if source_id is None:
        try:
            source_id = index_dataclass(g_sources, "active", False)
        except Exception as e:
            logger.warning("No free source id: %s", e)
            print("No free source id: ", e)
            return False
    
    if source_id >= MAX_NUM_SOURCES:
        raise IndexError("Source id out of range")

    # If source id is taken, find available source id
    # i = 0
    # while g_sources[source_id].active:
    #     if i > MAX_NUM_SOURCES:
    #         raise IndexError("Source id out of range")
    #     source_id = (source_id + 1) % MAX_NUM_SOURCES
    #     i += 1
    #     

    # Remove current source if current is placeholder
    if g_sources[source_id].bin is not None:
        remove_source(source_id)


    g_sources[source_id].active = False
    g_sources[source_id].eos = False
    g_sources[source_id].id = source_id


    if camera is not None:
        logger.info(f"Adding camera {camera.ip} at source {source_id}")

        if camera.ip == 'test':
            logger.debug(f"Adding test source at source {source_id}")
            source_bin = create_videotestsrc_source_bin(source_id)
            g_sources[source_id].name = "TestSource" + str(source_id)
            g_sources[source_id].type = SourceType.TEST
            
        elif camera.type == "Basler" or camera.type == "TheImagingSource":
            logger.debug(f"Adding {camera.type} camera {camera.ip} at source {source_id}")
            source_bin = create_aravis_source_bin(source_id, camera)
            # source_bin = create_aravis_source_device_bin(source_id, camera.ip)
            # source_bin = create_camgrabber_source_bin(source_id, camera.ip)
            g_sources[source_id].active = True
            g_sources[source_id].name = camera.ip
            g_sources[source_id].type = SourceType.BAYER       
    
        elif camera.type == "Compressed":
            logger.debug(f"Adding {camera.type} camera {camera.ip} at source {source_id}")
            if camera.uri is None:
                camera.uri = "rtsp://" + camera.ip + "/stream"
            source_bin = create_uridecodebin_source_bin(source_id, camera.uri)
            g_sources[source_id].active = True
            g_sources[source_id].uri = camera.uri
            g_sources[source_id].name = camera.ip
            g_sources[source_id].type = SourceType.RTSP

        else:
            logger.debug(f"Adding placeholder at source {source_id}")
            source_bin = create_placeholder_source_bin(source_id)
            g_sources[source_id].name = "Placeholder" + str(source_id)
            g_sources[source_id].type = SourceType.PLACEHOLDER

    else:
        logger.debug(f"Adding placeholder at source {source_id}")
        source_bin = create_placeholder_source_bin(source_id)
        g_sources[source_id].name = "Placeholder" + str(source_id)
        g_sources[source_id].type = SourceType.PLACEHOLDER


    if not source_bin:
        sys.stderr.write("Unable to create source bin\n")
        return False
    

    g_num_sources += 1
    g_sources[source_id].bin = source_bin

    logger.debug(f"Adding source {source_id} to pipeline")

    pipeline.add(source_bin)

    logger.debug(f"Added source {source_id} to pipeline")

    # Link source bin to streammux
    src_pad = source_bin.get_static_pad("src")
    sink_pad = streammux.request_pad_simple(f"sink_{source_id}")

    if src_pad.link(sink_pad) != Gst.PadLinkReturn.OK:
        sys.stderr.write("Unable to link source bin to streammux\n")
        return False  
    
    # if pipeline_pause_because_last_source:
        
    sync_return = source_bin.sync_state_with_parent()
    if not sync_return:
        logger.error("Unable to sync state with parent")
        source_bin.set_state(Gst.State.NULL)
        return False
    

    Gst.debug_bin_to_dot_file_with_ts(pipeline, Gst.DebugGraphDetails.ALL , "pipeline")

    return True

    if pipeline.get_state(Gst.CLOCK_TIME_NONE).state == Gst.State.PLAYING:
        state_return = source_bin.set_state(Gst.State.PLAYING)
        if state_return == Gst.StateChangeReturn.SUCCESS:
            print("Source added, now playing\n")
        elif state_return == Gst.StateChangeReturn.FAILURE:
            print("Source added, but unable to play\n")
            return False
        elif state_return == Gst.StateChangeReturn.ASYNC:
            state_return = g_sources[source_id].bin.get_state(Gst.CLOCK_TIME_NONE)
        elif state_return == Gst.StateChangeReturn.NO_PREROLL:
            print("STATE CHANGE NO PREROLL\n")

    return True
    


def remove_source(source_id: int):
    logger.debug(f"Stopping and releasing source {source_id} \n")
    global g_num_sources, g_sources, streammux, pipeline
    global pipeline_pause_because_last_source

    if g_sources[source_id].bin is None:
        return True

    # print_controller_port(g_sources[source_id].ip)

    # if g_num_sources == 1:
    #     logger.debug(f"Last source {source_id}. Pausing pipeline")
    #     pipeline_pause_because_last_source = True
    #     pipeline.set_state(Gst.State.PAUSED)

    # state_return = pipeline.set_state(Gst.State.NULL)
    state_return = g_sources[source_id].bin.set_state(Gst.State.NULL)

    bin = g_sources[source_id].bin

    print(f"state_return = {state_return}")

    if state_return == Gst.StateChangeReturn.SUCCESS:
        pad_name = "sink_%u" % source_id
        sinkpad = streammux.get_static_pad(pad_name)
        if sinkpad is not None:
            sinkpad.send_event(Gst.Event.new_eos())
        
            sinkpad.send_event(Gst.Event.new_flush_stop(False))
            streammux.release_request_pad(sinkpad)

        ret = pipeline.remove(bin)
        logger.debug(f"Removed source {source_id} from pipeline") if ret else logger.debug(f"Failed to remove source {source_id} from pipeline")
        g_num_sources -= 1
        g_sources[source_id].active = False
        g_sources[source_id].bin = None

        # return True


    elif state_return == Gst.StateChangeReturn.ASYNC:
        # Wait for the state change
        g_sources[source_id].bin.get_state(Gst.CLOCK_TIME_NONE)

        sinkpad = streammux.get_static_pad("sink_%u" % source_id)
        if sinkpad is not None:
            sinkpad.send_event(Gst.Event.new_eos())
            sinkpad.send_event(Gst.Event.new_flush_stop(False))
            streammux.release_request_pad(sinkpad)

        pipeline.remove(g_sources[source_id].bin)
        g_num_sources -= 1
        g_sources[source_id].active = False
        g_sources[source_id].bin = None

    else:
        logger.error("Unable to stop and release source %d" % source_id)

    # g_sources[source_id] = Source()

    


    if g_num_sources > 0:
        state_return = pipeline.set_state(Gst.State.PLAYING)

        if state_return == Gst.StateChangeReturn.SUCCESS:
            logger.debug("Source removed, now playing\n")  

        elif state_return == Gst.StateChangeReturn.FAILURE:
            logger.error("Unable to play after removing source %d" % source_id)




def setup_pipeline(stop_event: multiprocessing.Event):
    global g_num_sources, g_sources, pipeline_config
    global loop, pipeline, streammux, sink, nvvideoconvert, nvosd
    
    while not pipeline_config.ready():
        if stop_event.is_set():
            return
        
        time.sleep(1)

    logger.debug(f"Gstreamer initialized: {Gst.is_initialized()} \n")

    logger.info("Creating Pipeline \n")

    pipeline = Gst.Pipeline()
    if not pipeline:
        logger.error("Unable to create Pipeline \n")

    logger.info("Creating streammux \n")
    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    logger.debug("Created streammux \n")
    if not streammux:
        logger.error("Unable to create NvStreamMux \n")

    streammux.set_property("batched-push-timeout", 200000)
    streammux.set_property("batch-size", MAX_NUM_SOURCES)
    streammux.set_property("config-file-path", "../config/mux_config_source1.txt")
    streammux.set_property("sync-inputs", 0)
    
    logger.debug("Adding streammux \n")
    pipeline.add(streammux)
    logger.debug("Added streammux \n")

    # add_source(camera_name="10.1.3.75", source_id=1)
    # add_source(source_id=2)
    # add_source(camera_name="10.1.3.74")
    for i in range(MAX_NUM_SOURCES):
        add_source(source_id=i)


    logger.info("Creating queue \n")
    queue = Gst.ElementFactory.make("queue", "queue")
    if not queue:
        logger.error("Unable to create queue \n")

    logger.info("Creating tiler \n")
    tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
    if not tiler:
        logger.error(" Unable to create tiler \n")

    logger.info("Creating nvosd \n")
    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
    if not nvosd:
        logger.error(" Unable to create nvosd \n")

    logger.info("Creating nvvidconv \n")
    nvvideoconvert = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    if not nvvideoconvert:
        logger.error(" Unable to create nvvidconv \n")

    logger.info(f"Creating {SINK_ELEMENT} \n")
    sink = Gst.ElementFactory.make(SINK_ELEMENT, "sink")
    if not sink:
        logger.error(" Unable to create sink \n")

    queue.set_property("leaky", 1)
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)

    tiler.set_property("rows", TILER_ROWS)
    tiler.set_property("columns", TILER_COLS)
    tiler.set_property("width", OUTPUT_WIDTH)
    tiler.set_property("height", OUTPUT_HEIGHT)

    # fps_sink.set_property("video-sink", sink)
    # fps_sink.set_property("sync", False)
    # fps_sink.set_property("text-overlay", False)
    sink.set_property("sync", False)
    sink.set_property("enable-last-sample", False)
    sink.set_property("async", False)


    logger.info("Adding elements to Pipeline \n")
    pipeline.add(queue)
    pipeline.add(tiler)
    pipeline.add(nvosd)
    # pipeline.add(nvvideoconvert)
    pipeline.add(sink)

    logger.info("Linking elements in the Pipeline \n")
    streammux.link(queue)
    queue.link(tiler)
    tiler.link(nvosd)
    # nvosd.link(nvvideoconvert)
    nvosd.link(sink)

    loop = GLib.MainLoop()

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", message_handler, loop)

    pipeline.set_state(Gst.State.READY)


    print("Starting pipeline \n")
    state_ret = pipeline.set_state(Gst.State.PLAYING)

    if state_ret == Gst.StateChangeReturn.FAILURE:
        print("Unable to set the pipeline to the playing state")

    Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL , "pipeline")

    GLib.timeout_add(1000, check_sink_stats)

    logger.info("Starting main loop \n")

    loop.run()


    print("Stopping pipeline \n")
    pipeline.set_state(Gst.State.NULL)


def check_sink_stats():
    global sink, g_last_num_rendered_frames

    if not sink:
        return True
    
    stats = sink.get_property("stats")
    if not stats:
        return True

    avg_rate = stats.get_value("average-rate")
    dropped = stats.get_value("dropped")
    rendered = stats.get_value("rendered")

    delta = rendered - g_last_num_rendered_frames
    g_last_num_rendered_frames = rendered

    print(f"Average rate:    {avg_rate}        Dropped frames:    {dropped}        Rendered frames: {rendered}        FPS: {delta}")


    return True



def message_handler(bus, message, loop):
    global g_sources
    global pipeline
    t = message.type

    if t == Gst.MessageType.EOS:
        sys.stdout.write("End-of-stream\n")
        # loop.quit()
    elif t == Gst.MessageType.WARNING:
        err, debug = message.parse_warning()
        sys.stderr.write("Warning: %s: %s\n" % (err, debug))
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        sys.stderr.write("Error: %s: %s\n" % (err, debug))
        # loop.quit()
    elif t == Gst.MessageType.ELEMENT:
        struct = message.get_structure()
        if struct is not None and struct.has_name("stream-eos"):
            parsed, source_id = struct.get_uint("stream-id")
            if parsed:
                print("Got EOS from stream %d" % source_id)
                g_sources[source_id].eos = True
                # remove_source(source_id)
                # add_source(source_id) # Add placeholder source

    return True



if __name__ == "__main__":
    args = parser.parse_args()

    stop_event = multiprocessing.Event()
    message_queue = multiprocessing.Queue()

    config_file = args.config
    config = Config(config_file)

    mqtt_process = multiprocessing.Process(target=run_mqtt, args=(stop_event, message_queue, config.mqtt_config))
    mqtt_process.start()


    mqtt_handler_thread = threading.Thread(target=(mqtt_handler), args=(message_queue, stop_event))
    mqtt_handler_thread.start()

    pipe = setup_pipeline

    pipeline_thread = threading.Thread(target=(setup_pipeline), args=(stop_event,))
    pipeline_thread.start()


    try:
        print("\nProgram is running\n")
        stop_event.wait()
    except KeyboardInterrupt:
        stop_event.set()


    message_queue.put(None) # signal the queue to close
    logger.debug("Message queue closed")

    if loop:
        loop.quit()
        logger.debug("GLib main loop quit")

    pipeline_thread.join()
    logger.debug("Pipeline thread joined")

    mqtt_handler_thread.join()
    logger.debug("MQTT handler thread joined")

    mqtt_process.join()
    logger.debug("MQTT process joined")

