import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version('Aravis', '0.8')
from gi.repository import Gst, GLib, Aravis
from itertools import pairwise
from collections import OrderedDict
from typing import Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import pyds
import logging
import time
import math

# Initialize GStreamer
if not Gst.is_initialized():
    Gst.init(None)

# Configure logging
logger = logging.getLogger(__name__)

# Import custom modules
from VisionController.libs.camera import Camera
from VisionController.libs.gst.source_bins import (
    create_uridecodebin_source_bin,
    create_aravis_source_bin,
    create_placeholder_source_bin,
    create_videotestsrc_source_bin,
)
from VisionController.libs.utils import index_dataclass, scale, clamp, calculate_text_offset
from VisionController.libs.types import Source, SourceType
from VisionController.libs.gst.osd_manager import OSDManager

# Constants
MOVING_X = 0
MOVING_Y = 0

@dataclass
class Config:
    tiler_rows: int = 2
    tiler_cols: int = 2
    width: int = 3840
    height: int = 2160
    batch_size: int = 4
    streammux_config_file: Optional[str] = None
    max_num_sources: int = field(init=False)

    def __post_init__(self):
        self.max_num_sources = self.tiler_rows * self.tiler_cols

class PipelineManager:
    def __init__(self, config: Optional[dict] = None):
        self.config = Config(**config) if config else Config()
        self.pipeline = None
        self.elements = OrderedDict()
        self.sources = [Source(id=i, name=f"Source {i}") for i in range(self.config.max_num_sources)]
        self.osd_managers = [OSDManager((1920, 1080)) for _ in range(self.config.max_num_sources)]
        self.active_source_ips = []
        self.tiler_probe_ids = []
        self.last_num_rendered_frames = 0
        self.fps = 0
        self.loop = None

        # Initialize pipeline components
        self._create_pipeline()
        self._create_elements()
        self._link_elements()
        self._add_probes()
        self._fill_with_placeholders()

    def start(self):
        """Start the GStreamer pipeline and main loop."""
        self.loop = GLib.MainLoop()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._bus_message_handler)

        state_ret = self.pipeline.set_state(Gst.State.PLAYING)
        if state_ret == Gst.StateChangeReturn.FAILURE:
            logger.critical("Unable to set the pipeline to the playing state")
            return

        GLib.timeout_add(1000, self._print_fps)

        logger.info("Starting main loop")
        try:
            self.loop.run()
        except KeyboardInterrupt:
            logger.info("Pipeline stopped by user")
            self.stop()

    def stop(self):
        """Stop the GStreamer pipeline and clean up resources."""
        logger.debug("Stopping pipeline")
        if self.loop:
            self.loop.quit()

        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

        for osd_manager in self.osd_managers:
            osd_manager.stop()

        logger.info("Pipeline stopped")

    def _create_pipeline(self):
        """Create the GStreamer pipeline."""
        logger.info("Creating GStreamer Pipeline")
        self.pipeline = Gst.Pipeline()
        if not self.pipeline:
            logger.critical("Unable to create Pipeline")
            raise RuntimeError("Failed to create GStreamer pipeline")

    def _create_elements(self):
        """Create GStreamer elements and add them to the pipeline."""
        logger.info("Creating Elements")

        self.elements['streammux'] = Gst.ElementFactory.make("nvstreammux", "streammux")
        self.elements['tiler'] = Gst.ElementFactory.make("nvmultistreamtiler", "tiler")
        self.elements['nvosd'] = Gst.ElementFactory.make("nvdsosd", "osd")
        self.elements['sink'] = Gst.ElementFactory.make("nv3dsink", "sink")

        if not all(self.elements.values()):
            missing_elements = [name for name, elem in self.elements.items() if not elem]
            logger.error(f"Unable to create elements: {', '.join(missing_elements)}")
            raise RuntimeError("Failed to create GStreamer elements")

        for element in self.elements.values():
            self.pipeline.add(element)

        self._configure_elements()

    def _configure_elements(self):
        """Set properties for GStreamer elements."""
        streammux = self.elements['streammux']
        streammux.set_property("batch-size", self.config.batch_size)
        streammux.set_property("sync-inputs", False)
        streammux.set_property("batched-push-timeout", 200000)
        if self.config.streammux_config_file:
            streammux.set_property("config-file-path", self.config.streammux_config_file)

        tiler = self.elements['tiler']
        tiler.set_property("rows", self.config.tiler_rows)
        tiler.set_property("columns", self.config.tiler_cols)
        tiler.set_property("width", self.config.width)
        tiler.set_property("height", self.config.height)
        tiler.set_property("nvbuf-memory-type", 0)
        tiler.set_property("gpu-id", 0)

        nvosd = self.elements['nvosd']
        nvosd.set_property("process-mode", 1)

        sink = self.elements['sink']
        sink.set_property("sync", False)

    def _link_elements(self):
        """Link GStreamer elements in the pipeline."""
        logger.info("Linking Elements")
        element_list = list(self.elements.values())
        for src_elem, dst_elem in zip(element_list, element_list[1:]):
            if not src_elem.link(dst_elem):
                logger.error(f"Failed to link {src_elem.get_name()} to {dst_elem.get_name()}")
                raise RuntimeError("Failed to link pipeline elements")

    def _add_probes(self):
        """Add pad probes for handling buffers."""
        tiler = self.elements['tiler']
        tiler_sink_pad = tiler.get_static_pad("sink")
        if not tiler_sink_pad:
            logger.warning("Unable to get Tiler sink pad")
        else:
            probe_id = tiler_sink_pad.add_probe(Gst.PadProbeType.BUFFER, self._osd_manager_probe, None)
            self.tiler_probe_ids.append(probe_id)

    def _fill_with_placeholders(self):
        """Fill the pipeline with placeholder sources."""
        logger.info("Filling with placeholders")
        for source_id in range(self.config.max_num_sources):
            self.add_source(source_id)

    def add_source(self, source_id: int, camera: Optional[Camera] = None) -> bool:
        """Add a source to the pipeline."""
        logger.debug(f"Adding source {source_id}, camera: {camera}")

        if source_id >= self.config.max_num_sources:
            logger.error("Source ID out of range")
            return False

        if self.sources[source_id].bin:
            self.remove_source(source_id)

        source = self.sources[source_id]
        source.active = False
        source.eos = False
        source.id = source_id

        if camera:
            source.camera = camera
            source.ip = camera.ip
            source.name = camera.name

            if camera.ip == 'test':
                logger.debug(f"Adding test source at source {source_id}")
                source_bin = create_videotestsrc_source_bin(source_id)
                source.type = SourceType.TEST
            elif camera.type in ("Basler", "TheImagingSource"):
                logger.debug(f"Adding {camera.type} camera {camera.ip} at source {source_id}")
                source_bin = create_aravis_source_bin(source_id, camera)
                source.type = SourceType.BAYER
                arv_camera = source_bin.get_by_name(f"source-{camera.ip}").get_property("camera")
                source.arv_camera = arv_camera
                source.active = True
            elif camera.type == "Compressed":
                logger.debug(f"Adding {camera.type} camera {camera.ip} at source {source_id}")
                camera.uri = camera.uri or f"rtsp://{camera.ip}/stream-1.sdp"
                source_bin = create_uridecodebin_source_bin(source_id, camera.uri)
                source.type = SourceType.RTSP
                source.uri = camera.uri
                source.active = True
            else:
                logger.debug(f"Adding placeholder at source {source_id}")
                source_bin = create_placeholder_source_bin(source_id)
                source.type = SourceType.PLACEHOLDER
        else:
            logger.debug(f"Adding placeholder at source {source_id}")
            source_bin = create_placeholder_source_bin(source_id)
            source.name = f"Placeholder {source_id}"
            source.type = SourceType.PLACEHOLDER

        if not source_bin:
            logger.error(f"Unable to create source bin for source {source_id}")
            return False

        source.bin = source_bin
        self.pipeline.add(source_bin)
        self.active_source_ips.append(source.ip)

        # Link source bin to streammux
        src_pad = source_bin.get_static_pad("src")
        sink_pad = self.elements['streammux'].request_pad_simple(f"sink_{source_id}")

        if src_pad.link(sink_pad) != Gst.PadLinkReturn.OK:
            logger.error("Unable to link source bin to streammux")
            return False

        if not source_bin.sync_state_with_parent():
            logger.error("Unable to sync state with parent")
            source_bin.set_state(Gst.State.NULL)
            return False

        logger.debug(f"Source {source_id} added successfully")
        return True

    def remove_source(self, source_id: int) -> bool:
        """Remove a source from the pipeline."""
        logger.debug(f"Removing source {source_id}")
        source = self.sources[source_id]

        if not source.bin:
            logger.debug(f"Source {source_id} has no bin to remove")
            return True

        if source.ip in self.active_source_ips:
            self.active_source_ips.remove(source.ip)

        source_bin = source.bin
        source_bin.set_state(Gst.State.NULL)
        source_bin.get_state(Gst.CLOCK_TIME_NONE)

        pad_name = f"sink_{source_id}"
        sink_pad = self.elements['streammux'].get_static_pad(pad_name)
        if sink_pad:
            sink_pad.send_event(Gst.Event.new_eos())
            sink_pad.send_event(Gst.Event.new_flush_stop(False))
            self.elements['streammux'].release_request_pad(sink_pad)

        self.pipeline.remove(source_bin)
        source.bin = None
        source.active = False

        logger.debug(f"Source {source_id} removed")
        return True

    def _bus_message_handler(self, bus, message):
        """Handle GStreamer bus messages."""
        msg_type = message.type

        if msg_type == Gst.MessageType.EOS:
            logger.info("End-of-stream")
        elif msg_type == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            logger.warning(f"Warning: {err}: {debug}")
        elif msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Error: {err}: {debug}")
            self.stop()
        elif msg_type == Gst.MessageType.ELEMENT:
            struct = message.get_structure()
            if struct and struct.has_name("stream-eos"):
                parsed, source_id = struct.get_uint("stream-id")
                if parsed and not self.sources[source_id].eos:
                    logger.error(f"Unexpected EOS from stream {source_id}")
                    self.sources[source_id].eos = True
                    self.add_source(source_id)
        return True

    def _print_fps(self):
        """Print frames per second."""
        sink = self.elements['sink']
        if not sink:
            return True

        stats = sink.get_property("stats")
        if not stats:
            return True

        rendered = stats.get_value("rendered")
        delta = rendered - self.last_num_rendered_frames
        self.last_num_rendered_frames = rendered

        logger.info(f"FPS: {delta}")
        self.fps = delta

        return True

    def _osd_manager_probe(self, pad, info, user_data):
        """Probe function for OSD manager."""
        gst_buffer = info.get_buffer()
        if not gst_buffer:
            logger.warning("Unable to get GstBuffer")
            return Gst.PadProbeReturn.OK

        try:
            batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
            l_frame = batch_meta.frame_meta_list
            while l_frame:
                frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
                source_id = frame_meta.source_id
                display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
                osd_manager = self.osd_managers[source_id]

                # Handle text overlays
                texts = osd_manager.get_all_texts()
                if texts:
                    display_meta.num_labels = len(texts)
                    for i, text_dict in enumerate(texts):
                        label_meta = display_meta.text_params[i]
                        label_meta.display_text = text_dict["text"]
                        x_off = calculate_text_offset(
                            text_dict["text"], text_dict["font_size"], text_dict.get('alignment')
                        )
                        label_meta.x_offset = text_dict["x"] + x_off
                        label_meta.y_offset = text_dict["y"]
                        label_meta.font_params.font_name = text_dict["font_name"]
                        label_meta.font_params.font_size = text_dict["font_size"]
                        label_meta.font_params.font_color.set(*text_dict["font_color"])
                        label_meta.set_bg_clr = 1
                        label_meta.text_bg_clr.set(*text_dict["bg_color"])

                # Handle line overlays
                lines = osd_manager.get_all_lines_as_dicts()
                if lines:
                    display_meta.num_lines = len(lines)
                    for i, line_dict in enumerate(lines):
                        line_params = display_meta.line_params[i]
                        line_params.x1 = line_dict['x1']
                        line_params.y1 = line_dict['y1']
                        line_params.x2 = line_dict['x2']
                        line_params.y2 = line_dict['y2']
                        line_params.line_width = line_dict['line_width']
                        line_params.line_color.set(*line_dict['line_color'])

                pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
                l_frame = l_frame.next
        except Exception as e:
            logger.error(f"Exception in _osd_manager_probe: {str(e)}")

        return Gst.PadProbeReturn.OK

    # Additional methods (e.g., set_zoom, set_exposure_time) can be implemented here
    # ...

def main():
    """Main function to run the pipeline manager."""
    try:
        pipeline_manager = PipelineManager()
        pipeline_manager.start()
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
