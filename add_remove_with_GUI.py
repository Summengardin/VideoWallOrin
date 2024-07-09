import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version("Gtk", "4.0")
from gi.repository import Gst, GLib, Gtk

from libs.GUI.GUI import GUI
from libs.types import SourceType, Source
from libs.source_bins import create_uridecodebin_source_bin, create_aravis_source_bin, create_placeholder_source_bin, create_videotestsrc_source_bin
from libs.utils import index_dataclass, find_digits_in_string
from libs.MQTT.mqtt_client import MQTTClient

from functools import partial
import sys
import os
import threading
import yaml
import multiprocessing

import logging
logging.basicConfig(level=logging.DEBUG, format='%(message)s')
logger = logging.getLogger(__name__)


# Initialize GStreamer and GTK
Gst.init(None)
Gtk.init()


# Define constants
OUTPUT_WIDTH = 3840  
OUTPUT_HEIGHT = 2160
TILER_OUTPUT_ROWS = 2
TILER_OUTPUT_COLS = 2
GPU_ID = 0
MAX_NUM_SOURCES = 4
PLACEHOLDER_IMAGE = "assets/image_placeholder.png"
SINK_ELEMENT = "nv3dsink"
# SINK_ELEMENT = "xvimagesink"
PGIE_CONFIG_FILE = "DeepStream-Yolo/config_infer_primary_yoloV8.txt"


# Global variables
g_num_sources = 0
g_sources = [Source(id=i, name=f"Source {i}") for i in range(MAX_NUM_SOURCES)]
g_add_source_stage = 0
loop = None
pipeline = None
streammux = None
sink = None
nvvideoconvert = None
nvosd = None
tiler = None
pgie = None
gui = None
zoom_level = 0


example_files = ["assets/Sintel.mp4", "assets/image2.mp4", "assets/Big_Buck.mp4"]
cam_name = ""
cam_ips = ["10.1.3.74", "10.1.3.75", "10.1.3.76", "10.1.3.77"]
ip_to_serial = {"10.1.3.74": "40344360",
                "10.1.3.75": "46320531",    
                "10.1.3.76": "40336215",
                "10.1.3.77": "40341020"}


def initate_sources():
    for i in range(MAX_NUM_SOURCES):
        add_source(source_id=i)


def files_to_uri_list(files):
    cwd = os.getcwd()
    uri_list = [f"file://{cwd}/{file_path}" for file_path in files]

    return uri_list


def set_zoom_level(value):
    global zoom_level, pipeline
    zoom_level = value

    ip = "10.1.3.75"

    tcambin = pipeline.get_by_name(ip)
    properties = tcambin.get_property("tcam-properties")
    properties.set_value("Zoom", zoom_level)
    tcambin.set_property("tcam-properties", properties)


def add_source(uri: str = None, source_id: int = None, camera_name: str = None) -> bool:
    global g_sources
    global g_num_sources
    global pipeline
    global streammux
    global MAX_NUM_SOURCES

    
    # Find available source id
    if source_id is None:
        try:
            source_id = index_dataclass(g_sources, "active", False)
        except Exception as e:
            logger.warning("No free source id: %s", e)
            print("No free source id: ", e)
            return False
        
    if source_id >= MAX_NUM_SOURCES:
        raise IndexError("Source id out of range")

    cnt = 0

    while g_sources[source_id].active:
        source_id = (source_id + 1) % MAX_NUM_SOURCES
        cnt += 1
        if cnt > MAX_NUM_SOURCES:
            print("All sources enabled. Unable to add source")
            return False
        source_id = (source_id + 1) % MAX_NUM_SOURCES

    
    # Remove current source if current is dummy
    if g_sources[source_id].bin is not None and g_sources[source_id].active is False:
        stop_release_source(source_id)


    g_sources[source_id].active = False
    g_sources[source_id].eos = False


    if camera_name is not None:
        logger.info(f"Adding source {source_id} for camera: {camera_name}")
        # if camera_name == "10.1.3.75":
        g_sources, source_bin = create_aravis_source_bin(g_sources, source_id, camera_name)
        # else:
            # source_bin = create_aravis_bin(source_id, camera_name)
        g_sources[source_id].active = True
        g_sources[source_id].name = camera_name

    elif uri is not None:
        logger.info(f"Adding source {source_id} for URI: {uri}")
        g_sources, source_bin = create_uridecodebin_source_bin(g_sources, source_id, uri)
        g_sources[source_id].active = True
        g_sources[source_id].uri = uri
        g_sources[source_id].name = uri

    else:
        logger.info(f"Adding placeholder at source {source_id}")
        g_sources, source_bin = create_placeholder_source_bin(g_sources, source_id)
        g_sources[source_id].name = "placeholder"


    if not source_bin:
        sys.stderr.write("Failed to create source bin. Source not added")
        return False


    g_sources[source_id].bin = source_bin

    pipeline.add(source_bin)
    src_pad = source_bin.get_static_pad("src")
    sink_pad = streammux.request_pad_simple(f"sink_{source_id}")


    if src_pad.link(sink_pad) != Gst.PadLinkReturn.OK:
        sys.stderr.write(f"Unable to link source {source_id} to streammux \n")
        return False

    
    
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

    g_num_sources += 1

    for source in g_sources:
        print(source)

    return True



def stop_release_source(source_id):
    print(f"Stopping and releasing source {source_id} \n")
    global g_num_sources
    global g_source_bin_list
    global streammux
    global pipeline

    if g_sources[source_id].bin is None:
        return

    state_return = g_sources[source_id].bin.set_state(Gst.State.NULL)

    if state_return == Gst.StateChangeReturn.SUCCESS:
        pad_name = "sink_%u" % source_id
        sinkpad = streammux.get_static_pad(pad_name)
        if sinkpad is not None:
            sinkpad.send_event(Gst.Event.new_flush_start())
            sinkpad.send_event(Gst.Event.new_flush_stop(False))
            
            streammux.release_request_pad(sinkpad)

        pipeline.remove(g_sources[source_id].bin)
        g_num_sources -= 1
        g_sources[source_id].active = False
        g_sources[source_id].bin = None 


    elif state_return == Gst.StateChangeReturn.ASYNC:
        state_return = g_source_bin_list[source_id].get_state(Gst.CLOCK_TIME_NONE)
        pad_name = "sink_%u" % source_id
        sinkpad = streammux.get_static_pad(pad_name)
        if sinkpad is not None:
            sinkpad.send_event(Gst.Event.new_flush_stop(False))
            streammux.release_request_pad(sinkpad)

        pipeline.remove(g_source_bin_list[source_id])
        g_num_sources -= 1
        g_sources[source_id].active = False
        g_sources[source_id].bin = None 

    else:
        print("Unable to stop and release source %d" % source_id)


def bus_call(bus, message, loop):
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
                stop_release_source(source_id)

    return True





def main_pipeline(stop_event: multiprocessing.Event):

    global g_num_sources, g_source_bin_list, example_files, uri_list, g_sources
    global loop, pipeline, streammux, sink, nvvideoconvert, nvosd, tiler, pgie
    
    logger.debug(f"Gstreamer initialized: {Gst.is_initialized()} \n")

    if len(sys.argv) < 2:
        uri_list = files_to_uri_list(example_files)
    else:
        uri_list = sys.argv[1:]

    logger.info("Creating Pipeline \n")

    pipeline = Gst.Pipeline()
    if not pipeline:
        logger.error("Unable to create Pipeline \n")

    logger.info("Creating streammux \n")
    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    logger.debug("Created streammux \n")
    if not streammux:
        logger.error("Unable to create NvStreamMux \n")

    logger.debug("Setting streammux batched-push-timeout \n")

    streammux.set_property("batched-push-timeout", 20000)
    streammux.set_property("batch-size", MAX_NUM_SOURCES)
    streammux.set_property("config-file-path", "./mux_config_source1.txt")
    streammux.set_property("sync-inputs", 0)
    
    logger.debug("Adding streammux \n")
    pipeline.add(streammux)
    logger.debug("Added streammux \n")

    logger.debug("Creating sources \n")
    initate_sources()
    logger.debug("Created sources \n")

    # add_source(camera_name="10.1.3.75", source_id=1)
    # add_source(source_id=2)
    # add_source(camera_name="10.1.3.74")

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

    logger.info("Creating fpsdisplaysink \n")
    fps_sink = Gst.ElementFactory.make("fpsdisplaysink", "fps-sink")
    if not fps_sink:
        logger.error(" Unable to create fps_sink \n")

    queue.set_property("leaky", 1)
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)

    tiler.set_property("rows", TILER_OUTPUT_ROWS)
    tiler.set_property("columns", TILER_OUTPUT_COLS)
    tiler.set_property("width", OUTPUT_WIDTH)
    tiler.set_property("height", OUTPUT_HEIGHT)

    fps_sink.set_property("video-sink", sink)
    fps_sink.set_property("sync", False)
    fps_sink.set_property("text-overlay", False)


    logger.info("Adding elements to Pipeline \n")
    pipeline.add(queue)
    pipeline.add(tiler)
    pipeline.add(nvosd)
    # pipeline.add(nvvideoconvert)
    pipeline.add(fps_sink)

    logger.info("Linking elements in the Pipeline \n")
    streammux.link(queue)
    queue.link(tiler)
    tiler.link(nvosd)
    # nvosd.link(nvvideoconvert)
    nvosd.link(fps_sink)

    loop = GLib.MainLoop()

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    pipeline.set_state(Gst.State.PAUSED)

    print("Now playing...")
    for i, source in enumerate(g_sources):
        print(i, ": ", source.name)
    

    print("Starting pipeline \n")
    state_ret = pipeline.set_state(Gst.State.PLAYING)

    if state_ret == Gst.StateChangeReturn.FAILURE:
        print("Unable to set the pipeline to the playing state")
    
    # try:
    #     _ = index_dataclass(g_sources, "active", True)

    #     print("Starting pipeline \n")
    #     pipeline.set_state(Gst.State.PLAYING)
    # except ValueError:
    #     print("No source is active")
    #     pass

    logger.info("Starting main loop \n")

    loop.run()


    print("Stopping pipeline \n")
    pipeline.set_state(Gst.State.NULL)



def cb_add_remove_source(source_id, ip, button, state):
    print(f"\nButton {ip}: {state}\n")
    if state == "On":
        add_source(source_id=source_id, camera_name=ip)
    else:
        stop_release_source(source_id=source_id)

    

def run_gui():
    global gui
    global cam_ips

    labels = cam_ips
    callbacks = [partial(lambda i, button, state: cb_add_remove_source(source_id=i, ip=cam_ips[i], button=button, state=state), i) for i in range(len(cam_ips))]

    gui = GUI(btn_labels=labels, btn_callbacks=callbacks)
    gui.set_callback("zoom", set_zoom_level)

    gui.run()


def run_mqtt(stop_event):
    def parse_config(config_file):
        with open(config_file, 'r') as file:
            config = yaml.safe_load(file)
            return config
        
    mqtt_config = parse_config('libs/MQTT/mqtt_config.yml')
    broker = mqtt_config['broker']
    port = mqtt_config['port']
    root_topic = mqtt_config['camera_topic']
    subtopics = mqtt_config['subtopics']

    topics = [ (root_topic + subtopic, 1) for subtopic in subtopics ]

    mqtt_client = MQTTClient(broker, port, topics)
    mqtt_client.set_on_message_callback(mqtt_handler)
    try:
        mqtt_client.start()
    except TimeoutError:
        print("Connection to MQTT broker timed out.")
        return
    
    stop_event.wait()

    mqtt_client.stop()


def mqtt_handler(client, userdata, message):

    topic = message.topic
    payload = message.payload.decode("utf-8")
    topic_list = topic.split('/')

    print(f"MQTT: topic = {topic}, payload = {payload}")

    if topic_list[0] == 'CamObjects':
        try:
            index = find_digits_in_string(topic_list[1])
        except ValueError:
            logging.error("Could identify the index of the camera")
        
        if index is not None:
            if topic_list[2] == 'IP':
                # add_source(source_id=index, camera_name=payload)
                pass

    


def main():
    global loop
    stop_event = multiprocessing.Event()


    pipeline_thread = threading.Thread(target=main_pipeline, args=(stop_event,))
    mqtt_process = threading.Thread(target=run_mqtt, args=(stop_event,))

    pipeline_thread.start()
    mqtt_process.start()

    run_gui()

    stop_event.set()


    loop.quit()

    pipeline_thread.join()
    mqtt_process.join()



if __name__ == '__main__':
    main()



