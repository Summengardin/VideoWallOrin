import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GLib
from itertools import pairwise

import logging
logger = logging.getLogger(__name__)

from VisionController.libs.types import SourceType, Source, Camera
from VisionController.libs.gst.source_bins import create_uridecodebin_source_bin, create_aravis_source_bin, create_placeholder_source_bin, create_videotestsrc_source_bin
from VisionController.libs.utils import index_dataclass, find_digits_in_string, parse_config



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
        self.source_ips = []
        self.cameras = [Camera() for _ in range(10)]
        self.cameras[0] = Camera(ip="test", width=1920, height=1080, framerate=60) 
        self.last_num_rendered_frames = 0
        self.pipeline_pause_because_last_source = False


    def start(self):

        self._create_pipeline()
        self._create_elements()
        self._link_elements()   

        self._fill_with_placeholders()

        self.loop = GLib.MainLoop()

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._bus_message_handler, self.loop)


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


    def toggle_fullscreen(self, source_id):
        if self.tiler:
            self.tiler.set_property('show-source', source_id)

    def update_camera_features(self, camera_ip: str):
        try: 
            source_index = index_dataclass(self.sources, 'ip', camera_ip)
        except ValueError:
            logger.error(f"Source with camera at ip {camera_ip} not found")
            return

        self.sources[source_index].update_camera_features()

    def __update_camera_feature(self, camera_ip: str, setting: str, value):
        """For now, not used. Need to update feature system of aravis, to be able to set individual features

        :param camera_ip:   IP of the camera 
        :param setting:     Name of the feature
        :param value:       Value of the feature

        :return:            True if success, False if not 
        """
        if camera_ip not in self.source_ips:
            return False
        

        src = self.pipeline.get_by_name(f"source-{camera_ip}")
        if src is None:
            return False
        
        if setting == "exposure_time_auto":
            src.set_property("exposure-auto", value)
        elif setting == "exposure_time":
            src.set_property("exposure", value)
        elif setting == "gain_auto":
            src.set_property("gain-auto", value)
        elif setting == "gain":
            src.set_property("gain", value)
        else:
            return False
        
        return True
    
    def update_camera_feature(self, camera_ip: str, features: dict):
        """Updates the features of camera using aravis.set_property("features", )

        :param camera_ip:   IP of the camera 
        :param features:    Dictionary of features and values. For example: {"exposure_time_auto": 1, "exposure_time": 1000}

        :return:            True if success, False if not
        """
        if camera_ip not in self.source_ips:
            return False
        
        feature_str = " ".join([f"{key}={value}" for key, value in features.items()])
        src = self.pipeline.get_by_name(f"source-{camera_ip}")
        if src is None:
            return False
        
        src.set_property("features", feature_str)
        return True



    


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


    def add_source(self, source_id : int, camera : Camera = None):
            
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
        # i = 0
        # while self.sources[source_id].active:
        #     if i > MAX_NUM_SOURCES:
        #         raise IndexError("Source id out of range")
        #     source_id = (source_id + 1) % MAX_NUM_SOURCES
        #     i += 1
        #     
        # Remove current source if current is placeholder
        if self.sources[source_id].bin is not None:
            self.remove_source(source_id)


        self.sources[source_id].active = False
        self.sources[source_id].eos = False
        self.sources[source_id].id = source_id





        if camera is not None:
            logger.info(f"Adding camera {camera.ip} at source {source_id}")
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
            sys.stderr.write("Unable to create source bin\n")
            return False
        

        self.num_sources += 1
        self.sources[source_id].bin = source_bin

        logger.debug(f"Adding source {source_id} to pipeline")

        self.pipeline.add(source_bin)

        logger.debug(f"Added source {source_id} to pipeline")

        # Link source bin to streammux
        src_pad = source_bin.get_static_pad("src")
        sink_pad = self.streammux.request_pad_simple(f"sink_{source_id}")

        if src_pad.link(sink_pad) != Gst.PadLinkReturn.OK:
            sys.stderr.write("Unable to link source bin to streammux\n")
            return False  
        
        # if pipeline_pause_because_last_source:
            
        sync_return = source_bin.sync_state_with_parent()
        if not sync_return:
            logger.error("Unable to sync state with parent")
            source_bin.set_state(Gst.State.NULL)
            return False
        

        Gst.debug_bin_to_dot_file_with_ts(self.pipeline, Gst.DebugGraphDetails.ALL , "pipeline")

        self.source_ips.append(self.sources[source_id].ip)

        return True

        if pipeline.get_state(Gst.CLOCK_TIME_NONE).state == Gst.State.PLAYING:
            state_return = source_bin.set_state(Gst.State.PLAYING)
            if state_return == Gst.StateChangeReturn.SUCCESS:
                print("Source added, now playing\n")
            elif state_return == Gst.StateChangeReturn.FAILURE:
                print("Source added, but unable to play\n")
                return False
            elif state_return == Gst.StateChangeReturn.ASYNC:
                state_return = self.sources[source_id].bin.get_state(Gst.CLOCK_TIME_NONE)
            elif state_return == Gst.StateChangeReturn.NO_PREROLL:
                print("STATE CHANGE NO PREROLL\n")

        return True
    

    

        
    def remove_source(self, source_id: int):
        logger.debug(f"Removing source {source_id}")

        if self.sources[source_id].bin is None:
            return True
        
        if self.num_sources == 1:
            self.pipeline.set_state(Gst.State.PAUSED)
        
        bin = self.sources[source_id].bin
        self.source_ips.remove(self.sources[source_id].ip)

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

        

        # self.sources[source_id] = Source()

        # if self.num_sources > 0:
        #     state_return = self.pipeline.set_state(Gst.State.PLAYING)

        #     if state_return == Gst.StateChangeReturn.SUCCESS:
        #         logger.debug("Source removed, now playing\n")  

        #     elif state_return == Gst.StateChangeReturn.FAILURE:
        #         logger.error("Unable to play after removing source %d" % source_id)


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