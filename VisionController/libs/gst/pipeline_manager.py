import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GLib
from itertools import pairwise
import pyds

from dataclasses import dataclass 
from enum import Enum


import logging
logger = logging.getLogger(__name__)

from VisionController.libs.camera import Camera
from VisionController.libs.gst.source_bins import create_uridecodebin_source_bin, create_aravis_source_bin, create_placeholder_source_bin, create_videotestsrc_source_bin
from VisionController.libs.utils import index_dataclass, scale, clamp
from VisionController.libs.types import Source, SourceType


if Gst.is_initialized() == False:
    Gst.init(None)


class PipelineManager:
    def __init__(self, config = None):
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

        self.last_num_rendered_frames = 0
        self.pipeline_pause_because_last_source = False
        self.osd_frame_number = 0
        self.osd_text = "FRAME COUNT:  "

        self.exposure_auto_modes = ['Off', 'Once', 'Continuous']


    def start(self):

        self._create_pipeline()
        self._create_elements()
        self._link_elements()   

        self._fill_with_placeholders()

        self.loop = GLib.MainLoop()

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._bus_message_handler, self.loop)               

        # osd_sink_pad = self.nvosd.get_static_pad("sink")
        # if not osd_sink_pad:
        #     logger.warning("Unable to get Tiler sink pad")
        # else:            
        #     osd_sink_pad.add_probe(Gst.PadProbeType.BUFFER, self._osd_sink_pad_buffer_probe, None)


        state_ret = self.pipeline.set_state(Gst.State.PLAYING)

        Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL , "pipeline")

        if state_ret == Gst.StateChangeReturn.FAILURE:
            logger.critical("Unable to set the pipeline to the playing state")
            return

    
        GLib.timeout_add(1000, self._print_fps)

        logger.info("Starting main loop \n")

        self.loop.run()


    def stop(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            # Wait for state change to null
            self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

        if self.loop:
            self.loop.quit()
        
        print("=== Pipeline stopped ===\n")


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
            sys.stderr.write("Error: %s: %s\n" % (err, debug))
            # loop.quit()
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
        self.nvinfer = Gst.ElementFactory.make("nvinfer", "inference")        
        self.nvosd = Gst.ElementFactory.make("nvdsosd", "osd")
        self.tiler = Gst.ElementFactory.make("nvmultistreamtiler", "tiler")
        self.sink = Gst.ElementFactory.make("nv3dsink", "sink")

        self.elements = [self.streammux, self.nvosd, self.tiler, self.sink]

        for element in self.elements:
            if not element:
                logger.error(f"Unable to create {element.get_name()}")
                return
            self.pipeline.add(element)


        self.streammux.set_property("batch-size", self.batch_size)
        self.streammux.set_property("sync-inputs", False)
        self.streammux.set_property("batched-push-timeout", 200000)
        self.streammux.set_property("config-file-path", self.streammux_config_file)

        self.nvosd.set_property("process-mode", 2)
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

        for pair in pairwise(self.elements):
            if not pair[0].link(pair[1]):
                logger.error(f"Elements {pair[0].get_name()} and {pair[1].get_name()} couldn't be linked")


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
                self.sources[source_id].name = camera.ip
                self.sources[source_id].type = SourceType.BAYER   

                # try:
                #     aravis_element = source_bin.get_by_name(f"source-{camera.ip}")
                #     camera = aravis_element.get_property("camera")
                #     self.sources[source_id].arv_camera = camera
                #     print(self.sources[source_id].arv_camera)

                # except Exception as e:  
                #     logger.warning(f"Failed to get arv camera of {camera.ip}: {e}")

            elif camera.type == "Compressed":
                logger.debug(f"Adding {camera.type} camera {camera.ip} at source {source_id}")
                if camera.uri is None:
                    camera.uri = "rtsp://" + camera.ip + "/stream-1.sdp"
                source_bin = create_uridecodebin_source_bin(source_id, camera.uri)
                self.sources[source_id].active = True
                self.sources[source_id].uri = camera.uri
                self.sources[source_id].name = camera.ip
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
        logger.debug(f"Removing source {source_id}")

        if self.sources[source_id].bin is None:
            return True
        
        if self.num_sources == 1:
            self.pipeline.set_state(Gst.State.PAUSED)
        
        bin = self.sources[source_id].bin
        if self.sources[source_id].ip in self.active_source_ips:
            self.active_source_ips.remove(self.sources[source_id].ip)

        state_return = bin.set_state(Gst.State.NULL)

        if state_return == Gst.StateChangeReturn.FAILURE:
            logger.error(f"Failed to remove source {source_id} from pipeline")
            return False
        elif state_return == Gst.StateChangeReturn.ASYNC:
            bin.get_state(Gst.CLOCK_TIME_NONE)

        if state_return == Gst.StateChangeReturn.SUCCESS:
            self.sources[source_id].active = False
            pad_name = "sink_%u" % source_id
            sinkpad = self.streammux.get_static_pad(pad_name)
            if sinkpad is not None:
                self.sources[source_id].eos = True
                sinkpad.send_event(Gst.Event.new_eos())
                sinkpad.send_event(Gst.Event.new_flush_stop(False))
                self.streammux.release_request_pad(sinkpad)

            ret = self.pipeline.remove(bin)
            logger.debug(f"Removed source {source_id} from pipeline") if ret else logger.debug(f"Failed to remove source {source_id} from pipeline")
            self.num_sources -= 1
            self.sources[source_id].active = False
            self.sources[source_id].bin = None

        return True

        # self.sources[source_id] = Source()

        # if self.num_sources > 0:
        #     state_return = self.pipeline.set_state(Gst.State.PLAYING)

        #     if state_return == Gst.StateChangeReturn.SUCCESS:
        #         logger.debug("Source removed, now playing\n")  

        #     elif state_return == Gst.StateChangeReturn.FAILURE:
        #         logger.error("Unable to play after removing source %d" % source_id)


    def _update_features(self, camera_ip: str, features: dict):
        feature_str = " ".join([f"{key}={value}" for key, value in features.items()])


        src = self.pipeline.get_by_name(f"source-{camera_ip}")

        if src is None:
            logger.debug(f"Source {camera_ip} not found, cannot update features")
            return False    

        src.set_property("features", feature_str)

        return True


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


    def set_gain(self, camera_ip: str, gain: float):
        """
        Set the gain for a specific camera.

        :param camera_ip: The IP of the camera.
        :type camera_ip: str
        :param gain: The gain value. (0 - 1)
        :type gain: float
        """

        gain = clamp(gain, 0.0, 1.0)

        scaled = scale(gain, to_min=0.0, to_max=48.0)

        features = {"Gain": scaled}

        self._update_features(camera_ip, features)


    def set_exposure_auto(self, camera_ip: str, exposure_auto: str):
        """
        Set the exposure auto mode for a specific camera.

        :param camera_ip: The IP of the camera.
        :type camera_ip: str

        :param exposure_auto: The exposure auto mode. This can be one of the following: "Off", "Once", "Continuous"
        :type exposure_auto: str

        :return: True if the exposure auto mode was successfully set, False otherwise.
        :rtype: bool
        """

        if exposure_auto not in self.exposure_auto_modes:
            logger.warning(f"Camera {camera_ip}: Unknown exposure auto mode: {exposure_auto}")
            return False

        features = {"ExposureAuto": exposure_auto,
                    "GainAuto": exposure_auto}

        if exposure_auto != "Off":
            features["AutoExposureTimeUpperLimit"] = 20000.0
            features["AutoExposureTimeLowerLimit"] = 1.0
            features["AutoGainUpperLimit"] = 24.0
            features["AutoGainLowerLimit"] = 0.0
            features["AutoFunctionProfile"] = "MinimizeGain"
            features["AutoFunctionROISelector"] = "ROI1"
            features["AutoFunctionROIUseBrightness"] = True
            
        
        self._update_features(camera_ip, features)


    def set_target_brightness(self, camera_ip: str, brightness: float):
        """
        Set the target brightnes for a specific camera during auto exposure.

        :param camera_ip: The IP of the camera.
        :type camera_ip: str
        :param brightness: The target brightness value in unit interval (0 - 1).
        :type brightness: float
        """
        brightness = clamp(brightness, 0.0, 1.0)

        
        try:
            index = index_dataclass(self.sources, "ip", camera_ip)
        except:
            return False

        if self.sources[index].camera.type == "TheImagingSource":
            features = {"ExposureAutoReference": int(brightness*255)}
        else:
            self.target_brightness_upper_limit = 0.25
            self.target_brightness_lower_limit = 0.0

            brightness = scale(brightness, 0.0, 1.0, self.target_brightness_lower_limit, self.target_brightness_upper_limit)
            features = {"AutoTargetBrightness": brightness}

        self._update_features(camera_ip, features)


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


        return True
    

    
    def _osd_sink_pad_buffer_probe(self, pad, info, user_data):
        gst_buffer = info.get_buffer()
        if not gst_buffer:
            logger.warning("Unable to get GstBuffer ")
            return
        
        self.osd_frame_number += 1

        if self.osd_frame_number % 60 == 0:
            self.osd_text = f"Frame numbers: {self.osd_frame_number}"
            
        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
        l_frame = batch_meta.frame_meta_list
        while l_frame is not None:
            try:
                frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
            except StopIteration:
                break

            display_meta=pyds.nvds_acquire_display_meta_from_pool(batch_meta)
            display_meta.num_labels = 1
            py_nvosd_text_params = display_meta.text_params[0]

            py_nvosd_text_params.display_text = "Txt" +self.osd_text


            py_nvosd_text_params.x_offset = 10
            py_nvosd_text_params.y_offset = 12


            py_nvosd_text_params.font_params.font_name = "Serif"
            py_nvosd_text_params.font_params.font_size = 15

            py_nvosd_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)

            py_nvosd_text_params.set_bg_clr = 1

            py_nvosd_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 1.0)

            # print(f"Frame Number={frame_meta.frame_num}, No in batch={batch_meta.num_frames_in_batch}")

            pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)

            try:
                l_frame=l_frame.next
            except StopIteration:
                break

        return Gst.PadProbeReturn.OK