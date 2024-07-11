import time
import logging
import sys
from queue import Empty

from gi.repository import Gst, GLib

from libs.types import Source
from libs.utils import index_dataclass, find_digits_in_string

logger = logging.getLogger(__name__)

def main_pipeline(stop_event: multiprocessing.Event):
    global pipeline, streammux, sink, nvvideoconvert, nvosd, loop

    while not pipeline_config.ready():
        if stop_event.is_set():
            return
        time.sleep(1)

    logger.debug(f"Gstreamer initialized: {Gst.is_initialized()}")

    pipeline = Gst.Pipeline()
    if not pipeline:
        logger.error("Unable to create Pipeline")

    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    if not streammux:
        logger.error("Unable to create NvStreamMux")

    streammux.set_property("batched-push-timeout", 20000)
    streammux.set_property("batch-size", MAX_NUM_SOURCES)
    streammux.set_property("config-file-path", "./mux_config_source1.txt")
    streammux.set_property("sync-inputs", 0)
    pipeline.add(streammux)

    queue = Gst.ElementFactory.make("queue", "queue")
    tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
    nvvideoconvert = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    sink = Gst.ElementFactory.make(SINK_ELEMENT, "sink")
    fps_sink = Gst.ElementFactory.make("fpsdisplaysink", "fps-sink")

    if not all([queue, tiler, nvosd, nvvideoconvert, sink, fps_sink]):
        logger.error("Unable to create one or more elements")

    queue.set_property("leaky", 1)
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)
    tiler.set_property("rows", TILER_ROWS)
    tiler.set_property("columns", TILER_COLS)
    tiler.set_property("width", OUTPUT_WIDTH)
    tiler.set_property("height", OUTPUT_HEIGHT)
    fps_sink.set_property("video-sink", sink)
    fps_sink.set_property("sync", False)
    fps_sink.set_property("text-overlay", False)

    pipeline.add(queue, tiler, nvosd, fps_sink)
    streammux.link(queue)
    queue.link(tiler)
    tiler.link(nvosd)
    nvosd.link(fps_sink)

    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)
    pipeline.set_state(Gst.State.READY)

    while not pipeline_config.enable_pipeline:
        if stop_event.is_set():
            pipeline.set_state(Gst.State.NULL)
            return
        time.sleep(1)

    pipeline.set_state(Gst.State.PLAYING)
    loop.run()
    pipeline.set_state(Gst.State.NULL)

def bus_call(bus, message, loop):
    global g_sources
    t = message.type

    if t == Gst.MessageType.EOS:
        sys.stdout.write("End-of-stream\n")
    elif t == Gst.MessageType.WARNING:
        err, debug = message.parse_warning()
        sys.stderr.write("Warning: %s: %s\n" % (err, debug))
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        sys.stderr.write("Error: %s: %s\n" % (err, debug))
    elif t == Gst.MessageType.ELEMENT:
        struct = message.get_structure()
        if struct and struct.has_name("stream-eos"):
            parsed, source_id = struct.get_uint("stream-id")
            if parsed:
                logger.debug(f"Got EOS from stream {source_id}")
                g_sources[source_id].eos = True
                stop_release_source(source_id)

    return True
