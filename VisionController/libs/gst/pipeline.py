import sys
import time
import logging

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib


from libs.gst.source_bins import create_uridecodebin_source_bin, create_aravis_source_bin, create_placeholder_source_bin
from libs.utils import index_dataclass, find_digits_in_string
from libs.config.config import Config

Gst.init(None)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s:  %(message)s')
logger = logging.getLogger(__name__)

class GStreamerPipeline:
    def __init__(self, config: Config):
        self.config = config
        self.pipeline = Gst.Pipeline()
        self.streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
        self.queue = Gst.ElementFactory.make("queue", "queue")
        self.tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
        self.nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
        self.nvvideoconvert = Gst.ElementFactory.make("nvvideoconvert", "convertor")
        self.sink = Gst.ElementFactory.make("nv3dsink", "sink")
        self.fps_sink = Gst.ElementFactory.make("fpsdisplaysink", "fps-sink")

        self.setup_elements()
        self.g_sources = []
        self.g_num_sources = 0
        self.loop = None

    def setup_elements(self):
        if not self.pipeline:
            logger.error("Unable to create Pipeline")
        if not self.streammux:
            logger.error("Unable to create NvStreamMux")
        if not self.queue:
            logger.error("Unable to create Queue")
        if not self.tiler:
            logger.error("Unable to create Tiler")
        if not self.nvosd:
            logger.error("Unable to create OSD")
        if not self.nvvideoconvert:
            logger.error("Unable to create Convertor")
        if not self.sink:
            logger.error("Unable to create Sink")
        if not self.fps_sink:
            logger.error("Unable to create FPS Sink")

        self.streammux.set_property("batched-push-timeout", self.config['batched_push_timeout'])
        self.streammux.set_property("batch-size", self.config['batch_size'])
        self.streammux.set_property("sync-inputs", self.config['sync_inputs'])
        self.streammux.set_property("config-file-path", self.config['streammux_config'])

        self.queue.set_property("leaky", 1)
        self.queue.set_property("max-size-buffers", 1)
        self.queue.set_property("max-size-bytes", 0)
        self.queue.set_property("max-size-time", 0)

        self.tiler.set_property("rows", self.config['tiler_rows'])
        self.tiler.set_property("columns", self.config['tiler_columns'])
        self.tiler.set_property("width", self.config['width'])
        self.tiler.set_property("height", self.config['height'])

        self.fps_sink.set_property("video-sink", self.sink)
        self.fps_sink.set_property("sync", False)
        self.fps_sink.set_property("text-overlay", False)

        self.pipeline.add(self.streammux)
        self.pipeline.add(self.queue)
        self.pipeline.add(self.tiler)
        self.pipeline.add(self.nvosd)
        self.pipeline.add(self.fps_sink)

        self.streammux.link(self.queue)
        self.queue.link(self.tiler)
        self.tiler.link(self.nvosd)
        self.nvosd.link(self.fps_sink)

    def add_source(self, source_id, source_bin):
        logger.debug(f"Adding source {source_id} to pipeline")
        self.pipeline.add(source_bin)

        src_pad = source_bin.get_static_pad("src")
        sink_pad = self.streammux.request_pad_simple(f"sink_{source_id}")

        if src_pad.link(sink_pad) != Gst.PadLinkReturn.OK:
            logger.error("Unable to link source bin to streammux")
            return False

        if self.pipeline.get_state(Gst.CLOCK_TIME_NONE).state == Gst.State.PLAYING:
            state_return = source_bin.set_state(Gst.State.PLAYING)
            if state_return == Gst.StateChangeReturn.FAILURE:
                logger.error("Source added, but unable to play")
                return False
        return True

    def remove_source(self, source_id):
        logger.debug(f"Stopping and releasing source {source_id}")
        source_bin = self.g_sources[source_id].bin

        if source_bin:
            source_bin.set_state(Gst.State.NULL)
            pad_name = f"sink_{source_id}"
            sinkpad = self.streammux.get_static_pad(pad_name)
            if sinkpad:
                sinkpad.send_event(Gst.Event.new_flush_start())
                sinkpad.send_event(Gst.Event.new_flush_stop(False))
                self.streammux.release_request_pad(sinkpad)

            self.pipeline.remove(source_bin)
            self.g_sources[source_id].active = False
            self.g_sources[source_id].bin = None
            self.g_num_sources -= 1

    def run(self):
        self.loop = GLib.MainLoop()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.bus_call, self.loop)
        self.pipeline.set_state(Gst.State.READY)

        while not self.config['enable_pipeline']:
            time.sleep(1)

        logger.info("Starting pipeline")
        self.pipeline.set_state(Gst.State.PLAYING)
        self.loop.run()

        logger.info("Stopping pipeline")
        self.pipeline.set_state(Gst.State.NULL)

    def bus_call(self, bus, message, loop):
        t = message.type
        if t == Gst.MessageType.EOS:
            logger.info("End-of-stream")
        elif t == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            logger.warning(f"Warning: {err}: {debug}")
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Error: {err}: {debug}")
        elif t == Gst.MessageType.ELEMENT:
            struct = message.get_structure()
            if struct and struct.has_name("stream-eos"):
                parsed, source_id = struct.get_uint("stream-id")
                if parsed:
                    logger.info(f"Got EOS from stream {source_id}")
                    self.remove_source(source_id)
        return True
