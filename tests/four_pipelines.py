import multiprocessing
import time
import logging
import sys
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

sys.path.append('..')
from libs.gst.source_bins import create_aravis_source_bin, create_videotestsrc_source_bin

MAX_NUM_SOURCES = 4
SINK_ELEMENT = "autovideosink"
OUTPUT_WIDTH = 1920
OUTPUT_HEIGHT = 1080
TILER_ROWS = 2
TILER_COLS = 2

logger = logging.getLogger(__name__)

cam_names = ["10.1.3.75", "10.1.3.76", "10.1.3.77", None]
cam_names = [None]

MAX_NUM_SOURCES = len(cam_names)

Gst.init(None)

def message_handler(bus, message, loop):
    t = message.type
    if t == Gst.MessageType.EOS:
        logger.info("End-of-stream\n")
        loop.quit()
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        logger.error(f"Error: {err}, {debug}")
        loop.quit()

def add_source(pipeline, camera_name=None, source_id=0):
    logger.info(f"Adding source {source_id} \n")

    if camera_name:
        source = create_aravis_source_bin(source_id, camera_name)
        if not source:
            source = create_videotestsrc_source_bin(source_id)
    else:
        source = create_videotestsrc_source_bin(source_id)


    pipeline.add(source)
    return source

def setup_pipeline(stop_event: multiprocessing.Event, source_id: int, camera_name: str = None):

    logger.debug(f"Gstreamer initialized: {Gst.is_initialized()} \n")

    logger.info(f"Creating Pipeline for source {source_id} \n")

    pipeline = Gst.Pipeline()
    if not pipeline:
        logger.error("Unable to create Pipeline \n")

    source = add_source(pipeline, source_id=source_id, camera_name=camera_name)
    if not source:
        return

    logger.info("Creating nvvideoconvert \n")
    nvvideoconvert = Gst.ElementFactory.make("nvvideoconvert", f"convertor-{source_id}")
    if not nvvideoconvert:
        logger.error(f"Unable to create nvvidconv for source {source_id} \n")

    logger.info("Creating nvosd \n")
    nvosd = Gst.ElementFactory.make("nvdsosd", f"onscreendisplay-{source_id}")
    if not nvosd:
        logger.error(f"Unable to create nvosd for source {source_id} \n")

    # logger.info(f"Creating nv3dsink \n")
    # sink = Gst.ElementFactory.make("nv3dsink", f"sink-{source_id}")
    # if not sink:
    #     logger.error(f"Unable to create sink for source {source_id} \n")

    logger.info("Creating sink \n")
    sink = Gst.ElementFactory.make("nvdrmvideosink", f"sink-{source_id}")
    if not sink:
        logger.error(f"Unable to create sink for source {source_id} \n")


    # sink.set_property("sync", False)
    sink.set_property("enable-last-sample", False)
    x_pos = (source_id % TILER_COLS) * OUTPUT_WIDTH
    y_pos = (source_id // TILER_COLS) * OUTPUT_HEIGHT
    # sink.set_property("window-x", x_pos)
    # sink.set_property("window-y", y_pos)
    sink.set_property("offset-x", x_pos)
    sink.set_property("offset-y", y_pos)

    logger.info("Adding elements to Pipeline \n")
    pipeline.add(nvvideoconvert)
    pipeline.add(nvosd)
    pipeline.add(sink)

    logger.info("Linking elements in the Pipeline \n")
    source.link(nvvideoconvert)
    nvvideoconvert.link(nvosd)
    nvosd.link(sink)

    loop = GLib.MainLoop()

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", message_handler, loop)

    pipeline.set_state(Gst.State.READY)


    logger.info("Starting pipeline \n")
    state_ret = pipeline.set_state(Gst.State.PLAYING)

    if state_ret == Gst.StateChangeReturn.FAILURE:
        logger.error("Unable to set the pipeline to the playing state")

    Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL , f"pipeline-{source_id}")

    logger.info("Starting main loop \n")
    loop.run()

    logger.info("Stopping pipeline \n")
    pipeline.set_state(Gst.State.NULL)


def run_pipelines():
    stop_event = multiprocessing.Event()
    processes = []

    for i in range(MAX_NUM_SOURCES):
        p = multiprocessing.Process(target=setup_pipeline, args=(stop_event, i, cam_names[i]))
        processes.append(p)
        p.start()


    

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        stop_event.set()
        for p in processes:
            p.terminate()

    
    time.sleep(5)

    for i in range(MAX_NUM_SOURCES):
        p = multiprocessing.Process(target=setup_pipeline, args=(stop_event, i, cam_names[i]))
        processes.append(p)
        p.start()


    

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        stop_event.set()
        for p in processes:
            p.terminate()




if __name__ == "__main__":
    run_pipelines()
