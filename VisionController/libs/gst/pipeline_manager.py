import sys
import gi
import time
import gi.overrides.Gst
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
# gi.require_version('Aravis', '0.8')
import gi.overrides
from gi.repository import Gst, GLib#, Aravis
from itertools import pairwise
from collections import OrderedDict
from typing import Tuple
from dataclasses import dataclass 
from enum import Enum
from datetime import datetime
import pyds
import importlib
import re
import threading


import logging
logger = logging.getLogger(__name__)

# from VisionController.libs.gst.source_bins import create_uridecodebin_source_bin, create_aravis_source_bin, create_videotestsrc_source_bin
from VisionController.libs.cameras.placeholder_source_bin import create_source_bin as create_placeholder_source_bin
from VisionController.libs.cameras.nvuri_source_bin import create_source_bin as create_nvuri_source_bin
from VisionController.libs.utils import index_dataclass, scale, clamp, calculate_text_offset
from VisionController.libs.material_symbols import material_symbols
from VisionController.libs.vw_types import Source, SourceType, Camera
from VisionController.libs.gst.osd_manager import OSDManager

if Gst.is_initialized() == False:
    Gst.init(None)


class PipelineManager:
    def __init__(self, config = None):
        self.ready = False
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
        self.osd_managers = [OSDManager((1920, 1080)) for _ in range(self.max_num_sources)] 
        self.tiler_probe_ids = []
        self.monitor_timeout_id = None

        # Use RLock instead of Lock for reentrant locking
        self.source_lock = threading.RLock()

        self.last_num_rendered_frames = 0
        self.pipeline_pause_because_last_source = False
        self.osd_frame_number = 0
        self.osd_text = ""
        
        self.fps = 0
        self.last_fps_time = time.time()

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
            self.window_close_callback()
            return

        GLib.timeout_add(10000, self._print_fps)
        # GLib.timeout_add(5000, self._test_add_remove_source)

        self.start_monitoring()  # Start monitoring sources

        logger.info("Starting main loop \n")

        self.ready = True

        self.loop.run()
        

    def stop(self):
        logger.debug("=== Pipeline stopping ===")

        Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL , "final-pipeline")
        
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
        for osd_manager in self.osd_managers:
            osd_manager.stop()

        self.stop_monitoring()  # Stop monitoring sources
        logger.info("Pipeline stopped")

    def _elementwise_shutdown(self):
        logger.debug("Setting individual elements to NULL")
        if self.pipeline:
            try:
                for elem in self.pipeline.iterate_elements():
                    logger.debug(f"|--> Setting {elem.get_name()} to NULL")
                    elem.set_state(Gst.State.NULL)
            except gi.overrides.Gst.IteratorError as e:
                logger.warning(f"Caught IteratorError during elementwise shutdown: {e}")

    def _set_fullscreen(self, source_id):
        if self.tiler:
            self.tiler.set_property('show-source', source_id)


    def _bus_message_handler(self, bus, message, loop):
        t = message.type
        if t == Gst.MessageType.EOS:
            logger.debug("End-of-stream")
            # loop.quit()
        elif t == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            logger.warning(f"Warning {err}  Debug info: {debug}")
            match = re.search(r'GstBin:src(\d+)-bin', debug)
            if match:
                source_id = int(match.group(1))
            else:
                return

            if err.domain == "gst-resource-error-quark":
                if "The server closed the connection." in str(debug):
                    logger.error(f"Source {source_id} ({self.sources[source_id].ip}) closed the connection.")
                    self.remove_source(source_id)
                    self.add_source(source_id)  
                else:
                    logger.error(f"Above warning is due to error in source {source_id} ({self.sources[source_id].ip})")
                    self.remove_source(source_id)
                    self.add_source(source_id)

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
            print("Element message: ", struct)
            if struct is not None and struct.has_name("stream-eos"):
                parsed, source_id = struct.get_uint("stream-id")
                if parsed:
                    if self.sources[source_id].eos == False:
                        logger.error(f"Got unexpected EOS from stream {source_id}")
                        self.sources[source_id].eos = True
                        # self.add_source(source_id)
                        # print(f"\n\n\n ADED SOURCE {source_id} \n\n\n")                    

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
        # self.nvconvertsink = Gst.ElementFactory.make("nvvideoconvert", "nvvid-convert-sink")
        # self.sink = Gst.ElementFactory.make("xvimagesink", "sink")
        self.sink = Gst.ElementFactory.make("nveglglessink", "sink")
        # self.sink = Gst.ElementFactory.make("nvdrmvideosink", "sink")
       

        self.elements = OrderedDict({"streammux": self.streammux, 
                         "nvmultistreamtiler": self.tiler, 
                         "nvdsosd": self.nvosd, 
                        #  "nvvideoconvert": self.nvconvertsink,
                        #  "xvimagesink": self.sink})
                         "nveglglessink": self.sink})
                        #   "nvdrmvideosink": self.sink})

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
        self.streammux.set_property("max-latency", 1/60*1.01)
        self.streammux.set_property("config-file-path", self.streammux_config_file)
        self.streammux.set_property("batched-push-timeout", 16667)

        self.nvosd.set_property("gpu-id", 0)
        self.nvosd.set_property("process-mode", 1)
        self.nvosd.set_property("display-text", True)
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
            id = tiler_sink_pad.add_probe(Gst.PadProbeType.BUFFER, self._osd_manager_probe, None)
            # self.tiler_probe_ids.append(id)


    def _fill_with_placeholders(self):
        logger.info("Filling with placeholders")

        for source_id in range(self.max_num_sources):
            self.add_source(source_id)


    def _remove_source_internal(self, source_id: int) -> bool:
        """
        Internal implementation of source removal without locking.
        Should only be called from methods that already hold the source_lock.
        """
        if self.sources[source_id].bin is None or self.sources[source_id].in_removing_state:
            logger.debug(f"Source {source_id} is already in removing state, skipping")
            return True

        self.sources[source_id].in_removing_state = True
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
            pad_name = f"sink_{source_id}"
            sinkpad = self.streammux.get_static_pad(pad_name)
            if sinkpad is not None:
                logger.debug(f"Setting EOS for source {source_id}")
                self.sources[source_id].eos = True
                sinkpad.send_event(Gst.Event.new_eos())
                sinkpad.send_event(Gst.Event.new_flush_stop(False))
                logger.debug(f"Releasing source {source_id} from streammux")
                self.streammux.release_request_pad(sinkpad)

            ret = self.pipeline.remove(bin)
            if ret:
                logger.debug(f"Removed source {source_id} from pipeline")
                self.num_sources -= 1
                logger.debug(f"Source {source_id} removed, new num_sources = {self.num_sources}")
                self.sources[source_id].active = False
                self.sources[source_id].bin = None
            else:
                logger.debug(f"Failed to remove source {source_id} from pipeline")
            
        logger.debug(f"Finished removing source {source_id}")
        self.sources[source_id].in_removing_state = False
        return True

    def remove_source(self, source_id: int) -> bool:
        """
        Remove a source from the pipeline.

        Args:
            source_id (int): The ID of the source to remove.

        Returns:
            bool: True if the source was successfully removed, False otherwise.
        """

        logger.debug(f"Entered remove_source, source_id= {source_id}")
        with self.source_lock:
            return self._remove_source_internal(source_id)

    def add_source(self, source_id: int, camera: Camera = None, provider = None) -> bool:
        """
        Add a source to the pipeline.

        Args:
            source_id (int): The ID of the source to add. If None, the first available source ID will be used.
            camera (Camera, optional): The camera to add. If None, a placeholder source will be added.

        Returns:
            bool: True if the source was added successfully, False otherwise.
        """
        with self.source_lock:
            logger.debug(f"Add Source: source_id = {source_id}, camera = {camera}")
            
            if self.pipeline is None or self.streammux is None:
                return False

            if source_id is None:
                try:
                    source_id = index_dataclass(self.sources, "active", False)
                except Exception as e:
                    logger.warning("No free source id: %s", e)
                    return False
            
            if source_id >= self.max_num_sources:
                raise IndexError("Source id out of range")

            if (self.sources[source_id].type == "Placeholder" or self.sources[source_id].type == "Test") and (camera is None or camera.type == "Test") and self.sources[source_id].bin is not None:
                logger.debug(f"Already a placeholder or test source at {source_id}, skipping")
                return True

            self.sources[source_id].active = False
            self.sources[source_id].eos = False
            self.sources[source_id].id = source_id

            added_source = False

            if camera is not None and camera.provider is not None:
                self.sources[source_id].ip = camera.ip
                self.sources[source_id].camera = camera
                self.sources[source_id].type = camera.type

                try:
                    module_path = camera.provider.get("source_bin_path")
                    module_name = module_path.split("/")[-1].split(".")[0:-1][0]

                    if module_name in sys.modules:
                        source_bin_module = sys.modules[module_name]
                    else:
                        spec = importlib.util.spec_from_file_location(module_name, module_path)
                        source_bin_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(source_bin_module)
                        sys.modules[module_name] = source_bin_module
                        logger.debug(f"Imported module \"{module_name}\" for type \"{camera.type}\", {module_path}") 

                except ImportError as e:
                    logger.error(f"Unable to import source module for type \"{camera.type}\": {e}")
                    logger.debug("Adding placeholder source")
                    
                except AttributeError as e:
                    logger.error(f"Unable to import source module for type \"{camera.type}\": {e}")
                    logger.debug("Adding placeholder source")     

                else:
                    if camera.type == "Test":
                        source_bin = create_placeholder_source_bin(source_id, camera)
                        self.sources[source_id].active = False
                        
                    else:
                        source_bin = source_bin_module.create_source_bin(source_id, camera)
                        self.sources[source_id].active = True
                    
                    self.sources[source_id].name = camera.ip
                    

                    added_source = True
            
            if added_source == False:
                logger.debug(f"No camera source provided, adding placeholder at source {source_id}")
                source_bin = create_placeholder_source_bin(source_id, None)
                self.sources[source_id].name = "Placeholder" + str(source_id)
                self.sources[source_id].type = "Placeholder"

            if not source_bin:
                logger.error(f"Unable to create source bin for source {source_id}\n")
                return False
            
            # Remove the current bin if it exists
            if self.sources[source_id].bin is not None:
                if not self._remove_source_internal(source_id):
                    return False

            self.sources[source_id].bin = source_bin

            logger.debug(f"Adding source {source_id} to pipeline")
            self.num_sources += 1
            self.pipeline.add(source_bin)
            self.active_source_ips.append(self.sources[source_id].ip)

            logger.debug(f"Added source {source_id} to pipeline")

            # Link source bin to streammux. source_id decides pad, and therebye position in tiler
            src_pad = source_bin.get_static_pad("src")
            sink_pad = self.streammux.request_pad_simple(f"sink_{source_id}")

            if not src_pad:
                logger.error(f"Unable to get source pad from source bin {source_id}")
                return False
            if not sink_pad:   
                logger.error(f"Unable to get sink pad \"sink_{source_id}\" from streammux")
                return False

            try:
                ret = src_pad.link(sink_pad) == Gst.PadLinkReturn.OK
                if not ret:
                    logger.error(f"Unable to link source bin to streammux")
                    return False
            except Gst.LinkError as e:
                logger.error(f"Unable to link source bin to streammux: {e}")
                logger.debug(f"src_pad: {src_pad}, sink_pad: {sink_pad}")
                return False

            logger.debug(f"Linked source {source_id} to streammux")

            # Add bus connection for RTSP sources
            if self.sources[source_id].type != "Placeholder":
                bus = self.pipeline.get_bus()
                if bus:
                    bus.add_signal_watch()
                    bus.connect("message::error", self._handle_source_error, source_id)
                else:
                    logger.error(f"Unable to get pipeline bus for source {source_id}")

            sync_return = source_bin.sync_state_with_parent()
            logger.debug(f"Sync state with parent: {sync_return}")
            if not sync_return:
                logger.error("Unable to sync state with parent")
                source_bin.set_state(Gst.State.NULL)
                return False
            
            Gst.debug_bin_to_dot_file_with_ts(self.pipeline, Gst.DebugGraphDetails.ALL , "pipeline")

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
        current_time = time.time()
        
        delta = (rendered - self.last_num_rendered_frames) / (current_time - self.last_fps_time)
        self.last_num_rendered_frames = rendered
        self.last_fps_time = current_time

        print(f"FPS:    {round(delta)}")
        self.fps = delta

        return True


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

                
                osd_manager = self.osd_managers[source_id]

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

                texts = osd_manager.get_all_texts_as_dicts()
                if len(texts) > 0:

                    display_meta.num_labels = len(texts)
                    text_dicts = texts.copy()

                    for i in range(display_meta.num_labels):
                        try:
                            text_param = display_meta.text_params[i]
                            text_param.display_text = text_dicts[i]["text"]

                            x_off = 0
                            if text_dicts[i]['alignment'] is not None:
                                x_off = calculate_text_offset(text_dicts[i]["text"], text_dicts[i]["font_size"], text_dicts[i]['alignment'])
                            
                            text_param.x_offset = text_dicts[i]["x"]# + x_off
                            text_param.y_offset = text_dicts[i]["y"]
                            text_param.font_params.font_name = text_dicts[i]["font_name"]
                            text_param.font_params.font_size = text_dicts[i]["font_size"]
                            text_param.font_params.font_color.set(*text_dicts[i]["font_color"])
                            text_param.set_bg_clr = 1
                            text_param.text_bg_clr.set(*text_dicts[i]["bg_color"])
                        except Exception as e:
                            logger.error(f"Unable to display text, id: {i} : \"{text_dicts[i]['text']}\". \nError: {type(e)}: {e}")
                
                symbols = osd_manager.get_all_symbols_as_dicts()
                symbol_display_metas = [pyds.nvds_acquire_display_meta_from_pool(batch_meta) for _ in range(len(symbols) % 16 )]  # Max 16 elements per display meta
                
                for idx, symbol in enumerate(symbols):
                    symbol_meta = symbol_display_metas[idx // 16]
                    if idx % 16 == 0:
                        symbol_meta.num_labels = 16
                    text_params = symbol_meta.text_params[idx % 16]
                    text_params.display_text = symbol["symbol"]
                    text_params.x_offset = symbol["x"]
                    text_params.y_offset = symbol["y"]
                    text_params.font_params.font_name = symbol["font_name"]
                    text_params.font_params.font_size = symbol["font_size"]
                    text_params.font_params.font_color.set(*symbol["font_color"])
                    text_params.set_bg_clr = 1
                    text_params.text_bg_clr.set(*symbol["bg_color"])

                for meta in symbol_display_metas:
                    pyds.nvds_add_display_meta_to_frame(frame_meta, meta)
                
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

                # Display PTS (timestamp) of the current frame
                pts_time = frame_meta.buf_pts
                ntp_ts = frame_meta.ntp_timestamp
                pts_text = {
                    "text": f"Source: {source_id}  PTS: {pts_time}  NTP: {ntp_ts}",
                    "x": 10,
                    "y": 50,
                    "font_name": "Serif",
                    "font_size": 15,
                    "font_color": (1.0, 1.0, 1.0, 1.0),
                    "bg_color": (0.0, 0.0, 0.0, 0.6),
                    "alignment": None
                }

                # place in the middle of the screen of a 2x2 tile
                if source_id == 0:
                    pts_text["x"] = 1920
                    pts_text["y"] = 1050
                elif source_id == 1:
                    pts_text["x"] = 0
                    pts_text["y"] = 1080
                elif source_id == 2:
                    pts_text["x"] = 1920
                    pts_text["y"] = 30
                elif source_id == 3:
                    pts_text["x"] = 0
                    pts_text["y"] = 60
                    

                display_meta.num_labels += 1
                text_param = display_meta.text_params[display_meta.num_labels - 1]
                text_param.display_text = pts_text["text"]
                text_param.x_offset = pts_text["x"]
                text_param.y_offset = pts_text["y"]
                text_param.font_params.font_name = pts_text["font_name"]
                text_param.font_params.font_size = pts_text["font_size"]
                text_param.font_params.font_color.set(*pts_text["font_color"])
                text_param.set_bg_clr = 1
                text_param.text_bg_clr.set(*pts_text["bg_color"])

                pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
                
                try:
                    l_frame=l_frame.next
                except StopIteration:
                    break

        except Exception as e:
            logger.error(f"{type(e).__name__}Exception in _osd_manager_probe:  {str(e)}")

        return Gst.PadProbeReturn.OK
    
    def __del__(self):
        self.stop()

    def set_window_close_callback(self, callback):
        """Set a callback function to be called when window close is detected"""
        self.window_close_callback = callback

    def start_monitoring(self):
        """Start periodic monitoring of sources."""
        if self.monitor_timeout_id is None:
            self.monitor_timeout_id = GLib.timeout_add(1000, self.monitor_sources)  # Check every second
            logger.info("Started source monitoring")

    def stop_monitoring(self):
        """Stop periodic monitoring of sources."""
        if self.monitor_timeout_id is not None:
            GLib.source_remove(self.monitor_timeout_id)
            self.monitor_timeout_id = None
            logger.info("Stopped source monitoring")

    def monitor_sources(self):
        """Monitor all active sources for disconnections."""
        for source_id, source in enumerate(self.sources):
            if source.active and source.type == "RTSP":
                # Check if source is still active
                if source.bin and source.bin.get_state(Gst.CLOCK_TIME_NONE)[1] == Gst.State.NULL:
                    logger.warning(f"Detected disconnected source {source_id}")
                    self.handle_source_disconnection(source_id)
        return True

    def handle_source_disconnection(self, source_id: int) -> bool:
        """Handle a disconnected source by replacing it with a placeholder."""
        logger.info(f"Handling disconnection for source {source_id}")
        
        # Remove the disconnected source
        if not self.remove_source(source_id):
            logger.error(f"Failed to remove disconnected source {source_id}")
            return False
            
        # Add a placeholder source
        if not self.add_source(source_id):
            logger.error(f"Failed to add placeholder source for {source_id}")
            return False
            
        logger.info(f"Successfully replaced disconnected source {source_id} with placeholder")
        return True

    def _handle_source_error(self, bus, message, source_id):
        """Handle error messages from RTSP sources."""
        err, debug = message.parse_error()
        if message.src == self.sources[source_id].bin:
            logger.error(f"Error from source {source_id}: {err.message}")
            logger.debug(f"Debug info: {debug}")
            if "rtsp" in err.message.lower() or "connection" in err.message.lower():
                self.handle_source_disconnection(source_id)
        return True

    def _handle_source_state_change(self, bus, message, source_id):
        """Handle state changes from RTSP sources."""
        old_state, new_state, pending_state = message.parse_state_changed()
        if message.src == self.sources[source_id].bin:
            logger.debug(f"Source {source_id} state changed from {old_state.value_nick} to {new_state.value_nick}")
            if new_state == Gst.State.NULL:
                self.handle_source_disconnection(source_id)
        return True

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
