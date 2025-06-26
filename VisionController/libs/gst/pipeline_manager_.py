import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version('Aravis', '0.8')
from gi.repository import Gst, GLib, Aravis
from itertools import pairwise
from collections import OrderedDict
from typing import Tuple
from dataclasses import dataclass 
from enum import Enum
import pyds


import logging
logger = logging.getLogger(__name__)

from VisionController.libs.camera import Camera
from VisionController.libs.gst.source_bins import create_uridecodebin_source_bin, create_aravis_source_bin, create_placeholder_source_bin, create_videotestsrc_source_bin
from VisionController.libs.utils import index_dataclass, scale, clamp, calculate_text_offset
from VisionController.libs.types import Source, SourceType
from VisionController.libs.gst.osd_manager import OSDManager


if Gst.is_initialized() == False:
    Gst.init(None)


class PipelineManager:
    def __init__(self, config = None):
        self.window_close_callback = None

        self.config = config
        self._initiate_config()

        self.elements = []
        self.pipeline = None
        self.streammux = None
        self.sink = None
        self.nvinfer = None
        self.nvosd = None
        self.tiler = None
        self.loop = None
        self.num_sources = 0
        self.sources = [Source(id=i, name=f"Source {i}") for i in range(self.max_num_sources)]
        self.active_source_ips = []
        self.osd_manager = [OSDManager((1920, 1080)) for _ in range(self.max_num_sources)] 
        self.tiler_probe_ids = []

        self.last_num_rendered_frames = 0
        self.pipeline_pause_because_last_source = False
        self.osd_frame_number = 0
        self.osd_text = ""
        self.osd_text_dict = [
            {
                "text": "<Name of source>  <States>",
                "x": 0,
                "y": 200,
                "font_size": 18,
            },
            {
                "text": "Load: ",
                "x": 1920//2,
                "y": 200,
                "font_size": 18,
            },
            {
                "text": "<User set>",
                "x": 1920 - 200,
                "y": 200,
                "font_size": 18,
            },

            {
                "text": "<New setting> :  <Value>",
                "x": 1920//2,
                "y": 1080//2,
                "font_size": 48,
            },

        ]
        self.fps = 0

        self.exposure_auto_modes = ['Off', 'Once', 'Continuous']


    def start(self):

        self._create_pipeline()
        self._create_elements()
        self._link_elements()   
        self._add_probes()
        self._fill_with_placeholders()


        self.loop = GLib.MainLoop()

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._bus_message_handler, self.loop)           

       

        state_ret = self.pipeline.set_state(Gst.State.PLAYING)

        Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL , "pipeline")

        if state_ret == Gst.StateChangeReturn.FAILURE:
            logger.critical("Unable to set the pipeline to the playing state")
            logger.info("Have you set the DISPLAY variable?     export DISPLAY=:0")
            return

    
        GLib.timeout_add(1000, self._print_fps)

        logger.info("Starting main loop \n")

        self.loop.run()


    def stop(self):
        logger.debug("=== Pipeline stopping ===")
        
        # if len(self.tiler_probe_ids) > 0:
        #     print("Removing tiler probe")
        #     tiler_sink_pad = self.tiler.get_static_pad("sink")
        #     if not tiler_sink_pad:
        #         logger.warning("Unable to get Tiler sink pad")
        #     else:            
        #         # tiler_sink_pad.add_probe(Gst.PadProbeType.BUFFER, self._osd_sink_pad_buffer_probe, None)
        #         for probe_id in self.tiler_probe_ids:
        #             tiler_sink_pad = self.tiler.get_static_pad("sink")
        #             tiler_sink_pad.remove_probe(probe_id)
        #             print("Removed probe")
        
        if self.loop:
            logger.debug("Quitting main pipeline loop")
            self.loop.quit()

        if self.pipeline:
            # FIXME Without elemtnwise shutdown, the pipeline crashes with segmentation fault. This problemn occurs when the OSDManager is implemented.
            self._elementwise_shutdown()

            # print("Setting pipeline state to NULL")
            # self.pipeline.set_state(Gst.State.NULL)
            # print("Waiting for pipeline to stop")
            # self.pipeline.get_state(Gst.CLOCK_TIME_NONE)
        
        logger.debug("Stopping OSD managers")
        for osd_manager in self.osd_manager:
            osd_manager.stop()

        logger.info("Pipeline stopped")

    def _elementwise_shutdown(self):
        logger.error("Setting individual elements to NULL")
        if self.pipeline:
            for elem in self.pipeline.iterate_elements():
                logger.debug(f"|--> Setting {elem.get_name()} to NULL")
                elem.set_state(Gst.State.NULL)

    def _set_fullscreen(self, source_id):
        if self.tiler:
            self.tiler.set_property('show-source', source_id)


    def _bus_message_handler(self, bus, message, loop):
        t = message.type

        if t == Gst.MessageType.EOS:
            sys.stdout.write("End-of-stream\n")
            # loop.quit()
        elif t == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            sys.stderr.write("Warning: %s: %s\n" % (err, debug))
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Error: {err}: {debug}\n")            
            if err.message == "Output window was closed":
                logger.error("Window closed, notifying app")
                if self.window_close_callback:
                    self.window_close_callback()
                else:
                    logger.warning("No window close callback set")
            
        elif t == Gst.MessageType.ELEMENT:
            struct = message.get_structure()
            if struct is not None and struct.has_name("stream-eos"):
                parsed, source_id = struct.get_uint("stream-id")
                if parsed:
                    if self.sources[source_id].eos == False:
                        logger.error("Got unexpected EOS from stream %d" % source_id)
                        self.sources[source_id].eos = True
                        self.add_source(source_id)

        return True


    def _initiate_config(self):
        if self.config is None:
            self.config = {}

        self.tiler_rows = self.config.get('tiler_rows', 2)
        self.tiler_cols = self.config.get('tiler_cols', 2)
        self.width = self.config.get('width', 3840)
        self.height = self.config.get('height', 2160)
        self.batch_size = self.config.get('batch_size', 4)
        self.streammux_config_file = self.config.get('streammux_config', None)

        self.max_num_sources = self.tiler_rows * self.tiler_cols


    def _create_pipeline(self):
        logger.info("Creating GStreamer Pipeline")
        self.pipeline = Gst.Pipeline()
        if not self.pipeline:
            logger.critical("Unable to create Pipeline")
            return
    
    


    def _create_elements(self):
        logger.info("Creating Elements")
        
        self.streammux = Gst.ElementFactory.make("nvstreammux", "streammux")
        # self.nvinfer = Gst.ElementFactory.make("nvinfer", "inference")        
        self.tiler = Gst.ElementFactory.make("nvmultistreamtiler", "tiler")
        self.nvosd = Gst.ElementFactory.make("nvdsosd", "osd")
        self.sink = Gst.ElementFactory.make("nv3dsink", "sink")

        self.elements = OrderedDict({"streammux": self.streammux, 
                         "nvmultistreamtiler": self.tiler, 
                         "nvdsosd": self.nvosd, 
                         "nv3dsink": self.sink})

        # for element in self.elements:
        #     if not element:
        #         logger.error(f"Unable to create {self.get_var_name(element)}")
        #         return
        #     self.pipeline.add(element)

        for var_name, element in self.elements.items():
            if not element:
                logger.error(f"Unable to create {var_name}")
                return
            self.pipeline.add(element)


        self.streammux.set_property("batch-size", self.batch_size)
        self.streammux.set_property("sync-inputs", False)
        self.streammux.set_property("batched-push-timeout", 200000)
        self.streammux.set_property("config-file-path", self.streammux_config_file)

        self.nvosd.set_property("process-mode", 1)
        # self.nvosd.set_property("display-text", True)
        # self.nvosd.set_property("display-clock", True)
        # self.nvosd.set_property("clock-font-size", 30)
        # self.nvosd.set_property("x-clock-offset", 100)
        # self.nvosd.set_property("y-clock-offset", 100)

        self.tiler.set_property("rows", self.tiler_rows)
        self.tiler.set_property("columns", self.tiler_cols)
        self.tiler.set_property("width", self.width)
        self.tiler.set_property("height", self.height)
        self.tiler.set_property("nvbuf-memory-type", 0)
        self.tiler.set_property("gpu-id", 0)

        self.sink.set_property("sync", False)


    def _link_elements(self):
        logger.info("Linking Elements")

        for (var_name1, element1), (var_name2, element2) in pairwise(self.elements.items()):
            if not element1.link(element2):
                logger.error(f"Elements {var_name1} and {var_name2}  couldn't be linked")


    def _add_probes(self):
        tiler_sink_pad = self.tiler.get_static_pad("sink")
        if not tiler_sink_pad:
            logger.warning("Unable to get Tiler sink pad")
        else:            
            # id = tiler_sink_pad.add_probe(Gst.PadProbeType.BUFFER, self._osd_sink_pad_buffer_probe, None)
            id = tiler_sink_pad.add_probe(Gst.PadProbeType.BUFFER, self._osd_manager_probe, None)
            # self.tiler_probe_ids.append(id)


    def _fill_with_placeholders(self):
        logger.info("Filling with placeholders")

        for source_id in range(self.max_num_sources):
            self.add_source(source_id)


    def add_source(self, source_id: int, camera: Camera = None) -> bool:
        """
        Add a source to the pipeline.

        Args:
            source_id (int): The ID of the source to add. If None, the first available source ID will be used.
            camera (Camera, optional): The camera to add. If None, a placeholder source will be added.

        Returns:
            bool: True if the source was added successfully, False otherwise.
        """

        logger.debug(f"Add Source: source_id = {source_id}, camera = {camera}")

        if self.pipeline is None or self.streammux is None:
            return False

        if source_id is None:
            try:
                source_id = index_dataclass(self.sources, "active", False)
            except Exception as e:
                logger.warning("No free source id: %s", e)
                print("No free source id: ", e)
                return False
        
        if source_id >= self.max_num_sources:
            raise IndexError("Source id out of range")

        # If source id is taken, find available source id
        if self.sources[source_id].bin is not None:
            self.remove_source(source_id)

        self.sources[source_id].active = False
        self.sources[source_id].eos = False
        self.sources[source_id].id = source_id



        if camera is not None:
            self.sources[source_id].ip = camera.ip

            self.sources[source_id].camera = camera

            if camera.ip == 'test':
                logger.debug(f"Adding test source at source {source_id}")
                source_bin = create_videotestsrc_source_bin(source_id)
                self.sources[source_id].name = "TestSource" + str(source_id)
                self.sources[source_id].type = SourceType.TEST
                
            elif camera.type == "Basler" or camera.type == "TheImagingSource":
                logger.debug(f"Adding {camera.type} camera {camera.ip} at source {source_id}")
                source_bin = create_aravis_source_bin(source_id, camera)
                # source_bin = create_aravis_source_device_bin(source_id, camera.ip)
                # source_bin = create_camgrabber_source_bin(source_id, camera.ip)
                self.sources[source_id].active = True
                self.sources[source_id].name = camera.name
                self.sources[source_id].type = SourceType.BAYER

                arv_camera = source_bin.get_by_name(f"source-{camera.ip}").get_property("camera")
                self.sources[source_id].arv_camera = arv_camera

        
            elif camera.type == "Compressed":
                logger.debug(f"Adding {camera.type} camera {camera.ip} at source {source_id}")
                if camera.uri is None:
                    if camera.ip == "10.5.11.61":
                        camera.uri = "rtsp://10.5.11.61:8554/capture"
                    else:
                        camera.uri = "rtsp://" + camera.ip + "/stream-1.sdp"
                source_bin = create_uridecodebin_source_bin(source_id, camera.uri)
                self.sources[source_id].active = True
                self.sources[source_id].uri = camera.uri
                self.sources[source_id].name = camera.name
                self.sources[source_id].type = SourceType.RTSP

            else:
                logger.debug(f"Adding placeholder at source {source_id}")
                source_bin = create_placeholder_source_bin(source_id)
                self.sources[source_id].name = "Placeholder" + str(source_id)
                self.sources[source_id].type = SourceType.PLACEHOLDER

        else:
            logger.debug(f"Adding placeholder at source {source_id}")
            source_bin = create_placeholder_source_bin(source_id)
            self.sources[source_id].name = "Placeholder" + str(source_id)
            self.sources[source_id].type = SourceType.PLACEHOLDER



        if not source_bin:
            logger.error(f"Unable to create source bin fort source {source_id}\n")
            return False
        

        self.num_sources += 1
        self.sources[source_id].bin = source_bin

        logger.debug(f"Adding source {source_id} to pipeline")

        self.pipeline.add(source_bin)
        self.active_source_ips.append(self.sources[source_id].ip)

        logger.debug(f"Added source {source_id} to pipeline")

        # Link source bin to streammux
        src_pad = source_bin.get_static_pad("src")
        sink_pad = self.streammux.request_pad_simple(f"sink_{source_id}")

        if src_pad.link(sink_pad) != Gst.PadLinkReturn.OK:
            sys.stderr.write("Unable to link source bin to streammux\n")
            return False  



        sync_return = source_bin.sync_state_with_parent()
        if not sync_return:
            logger.error("Unable to sync state with parent")
            source_bin.set_state(Gst.State.NULL)
            return False
        

        Gst.debug_bin_to_dot_file_with_ts(self.pipeline, Gst.DebugGraphDetails.ALL , "pipeline")

        
        # After source has began playing, get min-max values of selected features
        # if self.sources[source_id].type == SourceType.BAYER:
        #     self.sources[source_id].limits['exposure_time_lower'], self.sources[source_id].limits['exposure_time_upper'] = self.get_exposure_bounds(source_id)
        #     self.sources[source_id].limits['gain_lower'], self.sources[source_id].limits['gain_upper'] = self.get_gain_bounds(source_id)
            
        #     if self.sources[source_id].camera.has_zoom:
        #         self.sources[source_id].limits['zoom_lower'], self.sources[source_id].limits['zoom_upper'] = self.get_zoom_bounds(source_id)
    
        return True

        if self.pipeline.get_state(Gst.CLOCK_TIME_NONE).state == Gst.State.PLAYING:
            state_return = source_bin.set_state(Gst.State.PLAYING)
            if state_return == Gst.StateChangeReturn.SUCCESS:
                logger.debug("Source added, now playing")
            elif state_return == Gst.StateChangeReturn.FAILURE:
                logger.debug("Source added, but unable to play")
                return False
            elif state_return == Gst.StateChangeReturn.ASYNC:
                state_return = self.sources[source_id].bin.get_state(Gst.CLOCK_TIME_NONE)
            elif state_return == Gst.StateChangeReturn.NO_PREROLL:
                logger.debug("STATE CHANGE NO PREROLL")

        return True
    

    def remove_source(self, source_id: int):
        """
        Remove a source from the pipeline.

        Args:
            source_id (int): The ID of the source to remove.

        Returns:
            bool: True if the source was successfully removed, False otherwise.
        """
        logger.debug(f"Entered remove_source, source_id= {source_id}")

        if self.sources[source_id].bin is None:
            logger.debug(f"Source {source_id} has no bin, skipping")
            return True
        
        if self.num_sources == 1:
            logger.debug(f"Only source {source_id} left, pausing pipeline")
            self.pipeline.set_state(Gst.State.PAUSED)
        
        bin = self.sources[source_id].bin
        if self.sources[source_id].ip in self.active_source_ips:
            logger.debug(f"Removing source {source_id} from active source IPs")
            self.active_source_ips.remove(self.sources[source_id].ip)

        logger.debug(f"Setting source {source_id} to NULL")
        state_return = bin.set_state(Gst.State.NULL)

        if state_return == Gst.StateChangeReturn.FAILURE:
            logger.error(f"Failed to change state of source {source_id} to NULL")
            return False
        elif state_return == Gst.StateChangeReturn.ASYNC:
            logger.debug(f"Waiting for source bin {source_id} to change state")
            bin.get_state(Gst.CLOCK_TIME_NONE)

        if state_return == Gst.StateChangeReturn.SUCCESS:
            logger.debug(f"Source {source_id} changed to NULL")
            self.sources[source_id].active = False
            pad_name = "sink_%u" % source_id
            sinkpad = self.streammux.get_static_pad(pad_name)
            if sinkpad is not None:
                logger.debug(f"Setting EOS for source {source_id}")
                self.sources[source_id].eos = True
                sinkpad.send_event(Gst.Event.new_eos())
                sinkpad.send_event(Gst.Event.new_flush_stop(False))
                logger.debug(f"Releasing source {source_id} from streammux")
                self.streammux.release_request_pad(sinkpad)

            ret = self.pipeline.remove(bin)
            logger.debug(f"Removed source {source_id} from pipeline") if ret else logger.debug(f"Failed to remove source {source_id} from pipeline")
            self.num_sources -= 1
            logger.debug(f"Source {source_id} removed, new num_sources = {self.num_sources}")
            self.sources[source_id].active = False
            self.sources[source_id].bin = None

        logger.debug(f"Finished removing source {source_id}")
        return True


    def _update_features(self, camera_ip: str, features: dict):
        feature_str = " ".join([f"{key}={value}" for key, value in features.items()])


        src = self.pipeline.get_by_name(f"source-{camera_ip}")

        if src is None:
            logger.debug(f"Source {camera_ip} not found, cannot update features")
            return False    

        src.set_property("features", feature_str)

        return True
    

    def get_exposure_bounds(self, source_id: int) -> Tuple[float, float]:
        """
        Get the exposure bounds for a specific source.

        :param source_id: The ID of the source.
        :type source_id: int

        :return: The exposure bounds in unit interval (0 - 1).
        :rtype: Tuple[float, float]

        """

        return self.sources[source_id].arv_camera.get_float_bounds("ExposureTime")
    



    def set_zoom(self, camera_ip: str, zoom: float):
        """
        Set the zoom for a specific source. If zoom is out of bounds, it will be clamped.

        :param camera_ip: The IP of the camera.
        :type camera_ip: str
        :param zoom: The zoom value in unit interval (0 - 1)
        :type zoom: float

        """
        
        if zoom < 0.0 : zoom = 0.0
        elif zoom > 1.0: zoom = 1.0
        
        scaled = int(zoom * 1000)
        features = {"Zoom": scaled}

        self._update_features(camera_ip, features)


    def set_exposure_time(self, camera_ip: str, exposure_time: float):
        """
        Set the exposure time for a specific camera during manual exposure.

        :param camera_ip: The IP of the camera.
        :type camera_ip: str
        :param exposure_time: The exposure time in unit interval (0 - 1).
        :type exposure_time: int
        """
        
        exposure_time = clamp(exposure_time, 0.0, 1.0)
        scaled = int(exposure_time * 20000)

        features = {"ExposureTime": scaled}

        self._update_features(camera_ip, features)
    

    def set_exposure_time_source(self, source_id: int, exposure_time: float):
        """
        Set the exposure time for a specific source during manual exposure.

        :param source_id: The ID of the source.
        :type source_id: int
        :param exposure_time: The exposure time in unit interval (0 - 1).
        :type exposure_time: int
        """
        
        exposure_time = clamp(exposure_time, 0.0, 1.0)
        lower = self.sources[source_id].arv_camera.get_float_bounds("ExposureTime")[0]
        scaled = int(exposure_time * 20000) + lower


        self.sources[source_id].arv_camera.set_float("ExposureTime", scaled)


    def set_gain_source(self, source_id: int, gain: float):
        """
        Set the gain for a specific source during manual exposure.
        
        :param source_id: The ID of the source.
        :type source_id: int
        
        :param gain: The gain in unit interval (0 - 1).
        :type gain: int
        """

        gain = clamp(gain, 0.0, 1.0)
        scaled = gain * 24

        self.sources[source_id].arv_camera.set_float("Gain", scaled)


    def set_exposure_auto_source(self, source_id: int, exposure_auto: str):
        """
        Set the exposure auto for a specific source during manual exposure.

        :param source_id: The ID of the source.
        :type source_id: int
        :param exposure_auto: The exposure auto mode.
        :type exposure_auto: str
        """

        arv_camera = self.sources[source_id].arv_camera

        arv_camera.set_string("ExposureAuto", exposure_auto)
        arv_camera.set_string("GainAuto", exposure_auto)

        if exposure_auto != "Off":
            if self.sources[source_id].camera.type == "Basler":
                arv_camera.set_float("AutoExposureTimeUpperLimit", 20000.0)
                arv_camera.set_float("AutoExposureTimeLowerLimit", 1.0)
                arv_camera.set_float("AutoGainUpperLimit", 24.0)
                arv_camera.set_float("AutoGainLowerLimit", 0.0)
                arv_camera.set_string("AutoFunctionProfile", "MinimizeGain")
                arv_camera.set_string("AutoFunctionROISelector", "ROI1")
                arv_camera.set_boolean("AutoFunctionROIUseBrightness", True)
            elif self.sources[source_id].camera.type == "TheImagingSource":
                arv_camera.set_boolean("ExposureAutoUpperLimitAuto", True) # Matches framerate
                arv_camera.set_float("ExposureAutoLowerLimit", 1.0)
                arv_camera.set_float("GainAutoUpperLimit", 24.0)
                arv_camera.set_float("GainAutoLowerLimit", 0.0)
                arv_camera.set_boolean("AutoFunctionsROIEnable", True)


    def set_target_brightness_source(self, source_id: int, target_brightness: float):
        """
        Set the target brightness for a specific source during auto exposure.

        :param source_id: The ID of the source.
        :type source_id: int
        :param target_brightness: The target brightness in unit interval (0 - 1).
        :type target_brightness: int
        """

        if self.sources[source_id].camera.type == "Basler":
            brightness = clamp(target_brightness, 0.0, 1.0)
            brightness = scale(brightness, to_min=0.015, to_max=0.5)
            self.sources[source_id].arv_camera.set_float("AutoTargetBrightness", brightness)
            
        elif self.sources[source_id].camera.type == "TheImagingSource":
            brightness = clamp(target_brightness, 0.0, 1.0)
            brightness = int(brightness * 255)
            self.sources[source_id].arv_camera.set_integer("ExposureAutoReference", brightness)


    def set_zoom_source(self, source_id: int, zoom: float):
        """
        Set the zoom for a specific source.

        :param source_id: The ID of the source.
        :type source_id: int
        :param zoom: The zoom value. (0 - 1)
        :type zoom: float
        """

        zoom = clamp(zoom, 0.0, 1.0)
        scaled = scale(zoom, to_min=0, to_max=1000)
        # scaled = scale(zoom, to_min=self.sources[source_id].limits['zoom_lower'], to_max=self.sources[source_id].limits['zoom_upper'])

        self.sources[source_id].arv_camera.set_integer("Zoom", int(scaled))


    def get_exposure_bounds(self, source_id: int) -> Tuple[float, float]:
        """
        Get the exposure bounds for a specific source.

        :param source_id: The ID of the source.
        :type source_id: int

        :return: The exposure bounds
        :rtype: Tuple[float, float]

        """

        return self.sources[source_id].arv_camera.get_float_bounds("ExposureTime")


    def get_gain_bounds(self, source_id: int) -> Tuple[float, float]:
        """
        Get the gain bounds for a specific source.

        :param source_id: The ID of the source.
        :type source_id: int

        :return: The gain bounds
        :rtype: Tuple[float, float]

        """

        return self.sources[source_id].arv_camera.get_float_bounds("Gain")
    

    def get_zoom_bounds(self, source_id: int) -> Tuple[int, int]:
        """
        Get the zoom bounds for a specific source.

        :param source_id: The ID of the source.
        :type source_id: int

        :return: The zoom bounds
        :rtype: Tuple[int, int]

        """

        return self.sources[source_id].arv_camera.get_integer_bounds("Zoom")

    def _print_fps(self):
        if not self.sink:
            return True
        
        stats = self.sink.get_property("stats")
        if not stats:
            return True

        avg_rate = stats.get_value("average-rate")
        dropped = stats.get_value("dropped")
        rendered = stats.get_value("rendered")

        delta = rendered - self.last_num_rendered_frames
        self.last_num_rendered_frames = rendered

        print(f"FPS:    {delta}")
        self.fps = delta


        return True
    

    
    def _osd_sink_pad_buffer_probe(self, pad, info, user_data):
        gst_buffer = info.get_buffer()
        if not gst_buffer:
            logger.warning("Unable to get GstBuffer ")
            return
        
        self.osd_frame_number += 1

        if self.osd_frame_number % 60 == 0:
            self.osd_text = f"Frame numbers: {self.osd_frame_number}"

        batch_text = ""
            
        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
        l_frame = batch_meta.frame_meta_list
        global moving_x, moving_y
        while l_frame is not None:

            try:
                frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
            except StopIteration:
                break

            pad_index = frame_meta.pad_index
            ntp_ts = frame_meta.ntp_timestamp
            font_size = 18

            
            display_meta=pyds.nvds_acquire_display_meta_from_pool(batch_meta)
            display_meta.num_labels = 5 + len(self.osd_text_dict)
            left_text_params = display_meta.text_params[0+len(self.osd_text_dict)]
            left_text2_params = display_meta.text_params[1+ len(self.osd_text_dict)]
            mid_text_params = display_meta.text_params[2+len(self.osd_text_dict)]
            right_text_params = display_meta.text_params[3+len(self.osd_text_dict)]
            setting_text_params = display_meta.text_params[4+len(self.osd_text_dict)]

            # for i in range (0, len(self.osd_text_dict)):
            #     display_meta.text_params[i].display_text = self.osd_text_dict[i]['text']

                
            #     display_meta.text_params[i].x_offset = self.osd_text_dict[i]['x']
            #     display_meta.text_params[i].y_offset = self.osd_text_dict[i]['y']

            #     display_meta.text_params[i].font_params.font_size = self.osd_text_dict[i]['font_size']
            #     display_meta.text_params[i].font_params.font_name = "Noto Serif Bold"
            #     display_meta.text_params[i].font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
            #     display_meta.text_params[i].set_bg_clr = 1
            #     display_meta.text_params[i].text_bg_clr.set(0.0, 0.0, 0.0, 0.6)                



            left_text = f"{self.sources[frame_meta.source_id].name:<20}   |   | X |   |   |"
            left_text_2 = f""
            mid_text = f"{self.osd_text}"
            right_text = f"Source: {self.sources[frame_meta.source_id].ip}"

            setting_text = "No Camera"
            if self.sources[frame_meta.source_id].camera:
                setting_text = f"Zoom :   {self.sources[frame_meta.source_id].camera.zoom}"


            left_text_params.display_text = left_text
            left_text2_params.display_text = left_text_2
            mid_text_params.display_text = mid_text
            right_text_params.display_text = right_text
            setting_text_params.display_text = setting_text

            left_text_params.x_offset = 0
            left_text_params.y_offset = 0

            left_text2_params.x_offset = 0
            left_text2_params.y_offset = font_size*2

            mid_text_params.x_offset = (1920 - len(mid_text) * font_size) // 2
            mid_text_params.y_offset = 0
            
            right_text_params.x_offset = 1920 - int(len(right_text) * font_size)
            right_text_params.y_offset = 0

            setting_text_params.x_offset = (1920 - int(len(setting_text) * font_size * 2) ) // 2
            setting_text_params.y_offset = 1080 - 100


        
            left_text_params.font_params.font_name = "Noto Serif Bold"
            left_text_params.font_params.font_size = font_size
            left_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
            left_text_params.set_bg_clr = 1
            left_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 0.6)

            left_text2_params.font_params.font_name = "Noto Serif Bold"
            left_text2_params.font_params.font_size = font_size
            left_text2_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
            left_text2_params.set_bg_clr = 1
            left_text2_params.text_bg_clr.set(0.0, 0.0, 0.0, 0.6)

            mid_text_params.font_params.font_name = "Noto Serif Bold"
            mid_text_params.font_params.font_size = font_size
            mid_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
            mid_text_params.set_bg_clr = 1
            mid_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 0.6)

            right_text_params.font_params.font_name = "Noto Serif Bold"
            right_text_params.font_params.font_size = font_size
            right_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
            right_text_params.set_bg_clr = 1
            right_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 0.6)

            setting_text_params.font_params.font_name = "Noto Serif Bold"
            setting_text_params.font_params.font_size = font_size * 2
            setting_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
            setting_text_params.set_bg_clr = 1
            setting_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 0.6)


            


            # Draw triangle

            display_meta.num_lines = 3
            line_params_1 = display_meta.line_params[0]
            line_params_2 = display_meta.line_params[1]
            line_params_3 = display_meta.line_params[2]



            # x1, y1 = 960 + moving_x, 400 + moving_y  # Top vertex
            # x2, y2 = 860 + moving_x, 600 + moving_y  # Bottom left vertex
            # x3, y3 = 1060 + moving_x, 600 + moving_y # Bottom right vertex
            moving_x = int(math.sin(time.time()) * 200)
            moving_y = int(math.cos(time.time()) * 200)
            triangle_x, triangle_y = 1920//2 + moving_x, 1080//2 + moving_y
            (x1, y1), (x2, y2), (x3, y3) = get_triangle_points(triangle_x, triangle_y, 100)

            line_params_1.x1, line_params_1.y1 = x1, y1
            line_params_1.x2, line_params_1.y2 = x2, y2
            line_params_1.line_width = 10
            line_params_1.line_color.set(1.0, 0.0, 0.0, 1.0)  # Red color

            line_params_2.x1, line_params_2.y1 = x2, y2
            line_params_2.x2, line_params_2.y2 = x3, y3
            line_params_2.line_width = 10
            line_params_2.line_color.set(1.0, 0.0, 0.0, 1.0)  # Red color

            line_params_3.x1, line_params_3.y1 = x3, y3
            line_params_3.x2, line_params_3.y2 = x1, y1
            line_params_3.line_width = 10
            line_params_3.line_color.set(1.0, 0.0, 0.0, 1.0)  # Red color





            pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)

            try:
                l_frame=l_frame.next
            except StopIteration:
                break
    

        return Gst.PadProbeReturn.OK


    def _osd_manager_probe(self, pad, info, user_data):
        gst_buffer = info.get_buffer()
        if not gst_buffer:
            logger.warning("Unable to get GstBuffer ")
            return

        
        global moving_x
        moving_x += 0.01


        try: 
            batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
            l_frame = batch_meta.frame_meta_list
            while l_frame is not None:

                try:
                    frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
                except StopIteration:
                    break

                display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta) 
                source_id = frame_meta.source_id

                osd_manager = self.osd_manager[source_id]
                
            #     text_dicts  = [ {
            #     "text": "LEFT TEXT",
            #     "x": 0,
            #     "y": 0,
            #     "font_size": 18,
            #     "font_color": (1.0, 1.0, 1.0, 1.0),
            #     "bg_color": (0.0, 0.0, 0.0, 0.6)
            # },
            # {
            #     "text": "RIGHT TEXT",
            #     "x": 1920 // 2,
            #     "y": 0,
            #     "font_size": 18,
            #     "font_color": (1.0, 1.0, 1.0, 1.0),
            #     "bg_color": (0.0, 0.0, 0.0, 0.6)
            # },
            # {
            #     "text": "MID TEXT",
            #     "x": 1920 - 200,
            #     "y": 0,
            #     "font_size": 18,
            #     "font_color": (1.0, 1.0, 1.0, 1.0),
            #     "bg_color": (0.0, 0.0, 0.0, 0.6)
            # }]

                texts = osd_manager.get_all_texts()
                if len(texts) > 0:

                    display_meta.num_labels = len(texts)
                    text_dicts = texts.copy()

                    for i in range(display_meta.num_labels):
                        label_meta = display_meta.text_params[i]
                        label_meta.display_text = text_dicts[i]["text"]


                        x_off = 0
                        if text_dicts[i]['alignment'] is not None:
                            x_off = calculate_text_offset(text_dicts[i]["text"], text_dicts[i]["font_size"], text_dicts[i]['alignment'])
                        
                        label_meta.x_offset = text_dicts[i]["x"] + x_off
                        label_meta.y_offset = text_dicts[i]["y"]
                        label_meta.font_params.font_name = text_dicts[i]["font_name"]
                        label_meta.font_params.font_size = text_dicts[i]["font_size"]
                        label_meta.font_params.font_color.set(*text_dicts[i]["font_color"])
                        label_meta.set_bg_clr = 1
                        label_meta.text_bg_clr.set(*text_dicts[i]["bg_color"])


                lines = osd_manager.get_all_lines_as_dicts()
                if len(lines) > 0:

                    display_meta.num_lines = len(lines)
                    
                    for i in range(display_meta.num_lines):
                        line_params = display_meta.line_params[i]
                        line_params.x1 = lines[i]['x1']
                        line_params.y1 = lines[i]['y1']
                        line_params.x2 = lines[i]['x2']
                        line_params.y2 = lines[i]['y2']
                        line_params.line_width = lines[i]['line_width']
                        line_params.line_color.set(*lines[i]['line_color'])


                # # Parameters for the warning triangle
                # offset_x = 100  # X-coordinate of the bottom left vertex of the triangle
                # offset_y = 100  # Y-coordinate of the bottom left vertex of the triangle
                # base_length = 200  # Length of the base of the triangle

                # display_meta = draw_warning_triangle(self.nvosd, display_meta, offset_x, offset_y, base_length)


                pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
                
                try:
                    l_frame=l_frame.next
                except StopIteration:
                    break

        except Exception as e:
            logger.error(f"Exception in _osd_manager_probe:  {str(e)}")

        return Gst.PadProbeReturn.OK
    
    def __del__(self):
        self.stop()


def get_triangle_points(center_x: int, center_y: int, size: int) -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]:
    """
    Returns three points (x,y) of a triangle, given a center position and size.
    """
    x1 = center_x - size
    y1 = center_y - size
    x2 = center_x
    y2 = center_y + size
    x3 = center_x + size
    y3 = center_y - size
    return (x1, y1), (x2, y2), (x3, y3)

import time
import math

moving_x = 0
moving_y = 0

def get_center_position(string_length, font_size, window_x, window_y):
    text_width = string_length * font_size * 1
    
    # Calculate the x position for centering
    x = (window_x - text_width) // 2
    
    # Calculate the y position for centering
    y = (window_y - font_size) // 2
    
    return int(x), y



def draw_warning_triangle(nvosd, display_meta, offset_x, offset_y, base_length):
    # Calculate triangle height based on equilateral triangle properties
    height = (math.sqrt(3) / 2) * base_length
    
    # Define the vertices of the triangle (offset by the given x, y)
    vertices = [
        (int(offset_x), int(offset_y)),  # Bottom left
        (int(offset_x + base_length), int(offset_y)),  # Bottom right
        (int(offset_x + base_length // 2), int(offset_y + height))  # Top center
    ]
    
    # Draw the triangle using three lines
    display_meta.num_lines = display_meta.num_lines + 3

    line_params1 = display_meta.line_params[display_meta.num_lines - 3]
    line_params1.x1, line_params1.y1 = vertices[0]
    line_params1.x2, line_params1.y2 = vertices[1]
    line_params1.line_width = 2
    line_params1.line_color.set(1.0, 0.0, 0.0, 1.0)  # Red color

    line_params2 = display_meta.line_params[display_meta.num_lines - 2]
    line_params2.x1, line_params2.y1 = vertices[1]
    line_params2.x2, line_params2.y2 = vertices[2]
    line_params2.line_width = 2
    line_params2.line_color.set(1.0, 0.0, 0.0, 1.0)  # Red color

    line_params3 = display_meta.line_params[display_meta.num_lines - 1]
    line_params3.x1, line_params3.y1 = vertices[2]
    line_params3.x2, line_params3.y2 = vertices[0]
    line_params3.line_width = 2
    line_params3.line_color.set(1.0, 0.0, 0.0, 1.0)  # Red color
    
    display_meta.num_circles = display_meta.num_circles + 1
    
    # Calculate the center of the triangle for the circle
    circle_center_x = int(offset_x + base_length // 2)
    circle_center_y = int(offset_y + height // 3)

    # Draw the circle
    circle_params = display_meta.circle_params[display_meta.num_circles - 1]
    circle_params.xc = circle_center_x
    circle_params.yc = circle_center_y
    circle_params.radius = base_length // 10
    circle_params.circle_color.set(1.0, 0.0, 0.0, 1.0)  # Red color

    return display_meta
