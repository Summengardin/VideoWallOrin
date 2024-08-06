import sys
import threading
import time
import logging
from queue import Empty
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import signal
import queue

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GLib

sys.path.append('..')
from libs.types import SourceType, Source, Camera
from libs.gst.source_bins import create_uridecodebin_source_bin, create_aravis_source_bin, create_placeholder_source_bin, create_videotestsrc_source_bin
from libs.utils import find_digits_in_string, parse_config, index_dataclass
from libs.mqtt.mqtt_client import MQTTClient

# Configure logging
logging.basicConfig(format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

Gst.init(None)

class PipelineManager:
    def __init__(self, config = None, streammux_config_file = None):
        self.config = config
        self.streammux_config_file = streammux_config_file
        self.initiate_config()

        self.elements = []
        self.pipeline = None
        self.streammux = None
        self.sink = None
        self.nvvideoconvert = None
        self.nvosd = None
        self.tiler = None
        self.loop = None
        self.num_sources = 0
        self.sources = [Source(id=i, name=f"Source {i}") for i in range(self.max_num_sources)]
        self.cameras = [Camera() for _ in range(10)]
        self.last_num_rendered_frames = 0
        self.pipeline_pause_because_last_source = False
    

    def initiate_config(self):
        if self.config is None:
            return
        
        self.tiler_rows = self.config.get('tiler_rows', 2)
        self.tiler_cols = self.config.get('tiler_cols', 2)
        self.width = self.config.get('width', 3840)
        self.height = self.config.get('height', 2160)
        self.batch_size = self.config.get('batch_size', 4)
        self.max_num_sources = self.tiler_rows * self.tiler_cols


    def setup_pipeline(self, stop_event):

        logger.info("Creating GStreamer Pipeline")
        self.pipeline = Gst.Pipeline()
        if not self.pipeline:
            logger.error("Unable to create Pipeline")
            return

        self.create_pipeline_elements()

        self.link_pipeline_elements()

        self.fill_with_placeholders()

        self.start_main_loop()


    def create_pipeline_elements(self):
        logger.info("Creating pipeline elements")
        self.streammux = Gst.ElementFactory.make("nvstreammux", "muxer")
        self.queue = Gst.ElementFactory.make("queue", "queue")
        self.tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
        self.nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
        self.nvvideoconvert = Gst.ElementFactory.make("nvvideoconvert", "convertor")
        self.sink = Gst.ElementFactory.make("nv3dsink", "sink")

        self.elements = [self.streammux, self.queue, self.tiler, self.nvosd, self.nvvideoconvert, self.sink]
        for element in self.elements:
            if not element:
                logger.error(f"Unable to create {element.get_name()}")
                return
            self.pipeline.add(element)

        self.queue.set_property("leaky", 1)
        self.queue.set_property("max-size-buffers", 1)

        self.streammux.set_property("batched-push-timeout", 200000)
        self.streammux.set_property("batch-size", self.max_num_sources)
        if self.streammux_config_file is not None:
            self.streammux.set_property("config-file-path", self.streammux_config_file)
        self.streammux.set_property("sync-inputs", False)

        self.tiler.set_property("rows", self.tiler_rows)
        self.tiler.set_property("columns", self.tiler_cols)
        self.tiler.set_property("width", self.width)
        self.tiler.set_property("height", self.height)

        self.sink.set_property("sync", False)
        self.sink.set_property("enable-last-sample", False)
        


    def link_pipeline_elements(self):
        logger.info("Linking elements in the Pipeline")

        for i in range (len(self.elements) - 1):    
            if not self.elements[i].link(self.elements[i+1]):
                logger.error(f"Unable to link {self.elements[i].get_name()} to {self.elements[i+1].get_name()}")
                return   
        

    def fill_with_placeholders(self):
        for i in range(self.max_num_sources):
            self.add_source(i)


    def add_source(self, source_id, camera=None):
        logger.debug(f"Adding source {source_id}, camera {camera}")
        if self.pipeline is None or self.streammux is None:
            return False

        if source_id >= self.max_num_sources:
            raise IndexError("Source id out of range")

        if self.sources[source_id].bin is not None:
            self.remove_source(source_id)

        source_bin = self.create_source_bin(source_id, camera)
        if not source_bin:
            logger.error("Unable to create source bin")
            return False

        self.num_sources += 1
        self.sources[source_id].bin = source_bin

        logger.debug(f"Adding source {source_id} to pipeline")
        self.pipeline.add(source_bin)

        src_pad = source_bin.get_static_pad("src")
        sink_pad = self.streammux.request_pad_simple(f"sink_{source_id}")

        if src_pad.link(sink_pad) != Gst.PadLinkReturn.OK:
            logger.error("Unable to link source bin to streammux")
            return False

        if source_bin.sync_state_with_parent() == Gst.StateChangeReturn.FAILURE:
            logger.error("Unable to sync state with parent")
            source_bin.set_state(Gst.State.NULL)
            return False

        Gst.debug_bin_to_dot_file_with_ts(self.pipeline, Gst.DebugGraphDetails.ALL, "pipeline")
        return True


    def create_source_bin(self, source_id, camera):
        if camera is not None:
            logger.info(f"Adding camera {camera.ip} at source {source_id}")
            if camera.ip == 'test':
                logger.debug(f"Adding test source at source {source_id}")
                source_bin = create_videotestsrc_source_bin(source_id)
                self.sources[source_id].name = "TestSource" + str(source_id)
                self.sources[source_id].type = SourceType.TEST
            elif camera.type in {"Basler", "TheImagingSource"}:
                logger.debug(f"Adding {camera.type} camera {camera.ip} at source {source_id}")
                source_bin = create_aravis_source_bin(source_id, camera)
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

        return source_bin


    def remove_source(self, source_id):
        logger.debug(f"Removing source {source_id}")
        if self.sources[source_id].bin is None:
            return True

        state_return = self.sources[source_id].bin.set_state(Gst.State.NULL)
        if state_return == Gst.StateChangeReturn.FAILURE:
            logger.error(f"Unable to stop and release source {source_id}")
            return False

        sinkpad = self.streammux.get_static_pad(f"sink_{source_id}")
        if sinkpad is not None:
            sinkpad.send_event(Gst.Event.new_eos())
            sinkpad.send_event(Gst.Event.new_flush_stop(False))
            self.streammux.release_request_pad(sinkpad)

        bin = self.sources[source_id].bin
        self.pipeline.remove(bin)

        self.num_sources -= 1
        self.sources[source_id].active = False
        self.sources[source_id].bin = None

        if self.num_sources > 0:
            if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
                logger.error(f"Unable to play after removing source {source_id}")

        return True

    def start_main_loop(self):
        self.loop = GLib.MainLoop()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.message_handler)

        self.pipeline.set_state(Gst.State.PLAYING)
        Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, "pipeline")

        GLib.timeout_add(1000, self.check_sink_stats)

        logger.info("Starting main loop")
        self.loop.run()


    def check_sink_stats(self):
        stats = self.sink.get_property("stats")
        if not stats:
            return True

        avg_rate = stats.get_value("average-rate")
        dropped = stats.get_value("dropped")
        rendered = stats.get_value("rendered")

        delta = rendered - self.last_num_rendered_frames
        self.last_num_rendered_frames = rendered

        logger.info(f"FPS:    {delta}")
        return True
    



    def message_handler(self, bus, message):
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
                    self.sources[source_id].eos = True
                    # self.remove_source(source_id)


    def fullscreen_toggler(self, source_id: int = None, state: bool = False):
        if state:
            logger.debug(f"Fullscreen on source {source_id}")
            self.tiler.set_property("show-source", source_id)
        else:
            logger.debug(f"Fullscreen off")
            self.tiler.set_property("show-source", -1)


    def update_camera_values(self, camera_ip : str = None):
        if camera_ip is None:
            return
        
        try:
            source_id = index_dataclass(self.sources, 'ip', camera_ip)
        except ValueError:
            print(f"Camera {camera_ip} not found")
            return
    
        self.sources[source_id].update_camera_values()    


    def stop(self):
        if self.loop:
            self.loop.quit()
        
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)


class MqttManager:
    def __init__(self, config, command_queue):
        self.config = config
        self.command_queue = command_queue

        self.broker = self.config.get('broker', 'localhost')
        self.port = self.config.get('port', 1883)

        cameras = self.config['cameras']
        camera_subtopics = self.config['camera_subtopics']
        vision_controllers = self.config['vision_controllers']
        vision_controller_subtopics = self.config['vision_controller_subtopics']

        topics = self._build_topics(cameras, camera_subtopics, vision_controllers, vision_controller_subtopics)

        self.client = MQTTClient(self.broker, self.port, topics)
        self.client.handler = self._message_handler
        

    def start(self):
        self.client.start()


    def stop(self):
        self.client.stop()

    def _message_handler(self, message):
        payload = message.payload.decode('utf-8')
        logger.debug(f"MQTT message on topic: {message.topic}: {payload}")
        self.command_queue.put((message.topic, payload))

    def _build_topics(self, cameras, camera_subtopics, vision_controllers, vision_controller_subtopics):
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
                if isinstance(subtopic, dict):
                    topic = list(subtopic.keys())[0]
                    qos = subtopic[topic]
                    topics.append((vision_controller + topic, qos))
                else:
                    topics.append((vision_controller + subtopic, 0))

        return topics


class MQTTHandler:
    def __init__(self, command_queue, pipeline_manager, stop_event):
        self.command_queue = command_queue
        self.pipeline_manager = pipeline_manager
        self.stop_event = stop_event

        self.running = True

    def start(self):
        while self.running:
            try:
                msg = self.command_queue.get(timeout=1)
                if msg is None:
                    break
                topic, payload = msg
                logger.debug(f"Dequeued message on topic: {topic}: {payload}")
                self._process_message(topic, payload)
            except ValueError:
                logger.error("No message in queue")
            except Empty:
                continue


    def stop(self):
        self.running = False


    def _process_message(self, topic, payload):
        topic_split = topic.split('/')
        root_topic = topic_split[0]

        if root_topic == 'VisionControllers':
            self._handle_vision_controllers_message(topic_split, payload, self.stop_event)
        elif root_topic == 'CamObjects':
            self._handle_cam_objects_message(topic_split, payload)

    

    def _handle_vision_controllers_message(self, topic_split, payload):
        command = topic_split[2]
        if command == 'Shutdown' and int(payload) > 0:
            logger.debug("Stop event set")
            self.stop_event.set()
            self.stop()
        elif command == 'Fullscreen':
            self.pipeline_manager.toggle_fullscreen(int(payload))
        elif command in {'Width', 'Height', 'TilerRows', 'TilerColumns'}:
            self.update_pipeline_config(command, payload)
        elif command == 'StartPipeline' and int(payload) > 0:
            self.pipeline_manager.enable_pipeline = True
            logger.debug(f"Pipeline enabled: {self.pipeline_manager.enable_pipeline}")
        elif command.startswith('Tile'):
            self._handle_tile_command(command, topic_split, payload)


    def _update_pipeline_config(self, command, payload):
        value = int(payload)
        if command == 'Width':
            self.pipeline_manager.width = value
        elif command == 'Height':
            self.pipeline_manager.height = value
        elif command == 'TilerRows':
            self.pipeline_manager.tiler_rows = value
        elif command == 'TilerColumns':
            self.pipeline_manager.tiler_cols = value
        logger.debug(f"{command} set to {value}")


    def _handle_tile_command(self, command, topic_split, payload):
        index = find_digits_in_string(command)
        source_id = index - 1
        subcommand = topic_split[3]

        if index is not None:
            if subcommand == 'Source':
                camera_index = find_digits_in_string(payload)
                self.pipeline_manager.sources[source_id].camera = self.pipeline_manager.cameras[camera_index]
            elif subcommand == 'Enable':
                if int(payload) > 0:

                    try:
                        success = self._run_with_timeout(self.pipeline_manager.add_source, args=(source_id,), kwargs={'camera': self.pipeline_manager.sources[source_id].camera})
                        if not success:
                            logger.error(f"Adding source {source_id} timed out")
                            success = self._run_with_timeout(self.pipeline_manager.add_source, args=(source_id,))
                            if not success:
                                logger.error(f"Adding placeholder source {source_id} timed out")
                    except Exception as e:
                        logger.error(f"Could not add source {source_id}")
                        traceback.print_exc()
                        success = self._run_with_timeout(self.pipeline_manager.add_source, args=(source_id,))
                        if not success:
                            logger.error(f"Adding placeholder source {source_id} timed out")
                        

                else:
                    try:
                        success = self._run_with_timeout(self.pipeline_manager.remove_source, args=(source_id,))
                        if not success:
                            logger.error(f"Removing source {source_id} timed out")
                        success = self._run_with_timeout(self.pipeline_manager.add_source, args=(source_id,))
                        if not success:
                            logger.error(f"Adding placeholder source {source_id} timed out")
                    except Exception as e:
                        logger.error(f"Could not stop releasing source {source_id}")
                        traceback.print_exc()

    def _handle_cam_objects_message(self, topic_split, payload):
        index = find_digits_in_string(topic_split[1])
        command = topic_split[2]
        camera = self.pipeline_manager.cameras[index]

        if command == 'IP':
            camera.ip = payload
        elif command == 'Type':
            camera.type = payload
            camera.has_zoom = payload == 'TheImagingSource'
        elif command == 'Width':
            camera.width = int(payload)
        elif command == 'Height':
            camera.height = int(payload)
        elif command == 'Format':
            camera.format = payload
        elif command == 'Framerate':
            camera.framerate = float(payload)
        elif command == 'Zoom':
            camera.zoom = int(payload)
        elif command == 'Exposure':
            camera.exposure_time = float(payload)
        elif command == 'ExposureAuto':
            camera.exposure_time_auto = 2 if int(payload) > 0 else 0
        elif command == 'Gain':
            camera.gain = float(payload)
        elif command == 'GainAuto':
            camera.gain_auto = 2 if int(payload) > 0 else 0

        self._run_with_timeout(self.pipeline_manager.update_camera_values, args=(camera.ip,))


    def _run_with_timeout(self, func, args=(), kwargs={}, timeout=5):
        """Runs a function asynchronously with a timeout."""
        future = self.executor.submit(func, *args, **kwargs)

        try:
            result = future.result(timeout=timeout)
            return result
        except TimeoutError:
            logger.error(f"Function {func.__name__} timed out")
            return False
        except Exception as e:
            logger.error(f"Function {func.__name__} raised an exception: {e}")
            raise e


class App:
    def __init__(self, config_file = '../config/config.yml', streammux_config_file = '../config/streammux_config.yml'):
        self.config = parse_config(config_file)
        self.pipeline_config = self.config['pipeline']
        self.mqtt_config = self.config['mqtt']

        self.stop_event = threading.Event()
        self.message_queue = queue.Queue() 

        self.pipeline_manager = PipelineManager(self.pipeline_config, streammux_config_file)
        self.mqtt_manager = MqttManager(self.mqtt_config, self.message_queue)
        self.mqtt_handler = MQTTHandler(self.message_queue, self.pipeline_manager, self.stop_event)

           
        # signal.signal(signal.SIGINT, self.shutdown_handler)
        # signal.signal(signal.SIGTERM, self.shutdown_handler)


    def start(self):

        self.pipeline_thread = threading.Thread(target=self.pipeline_manager.setup_pipeline, args=(self.stop_event,))
        self.pipeline_thread.start()

        self.mqtt_thread = threading.Thread(target=self.mqtt_manager.start)
        self.mqtt_thread.start()


        time.sleep(3)
        self.mqtt_handler_thread = threading.Thread(target=self.mqtt_manager.start)
        self.mqtt_handler_thread.start()


    def stop(self):
        logger.info("Stopping app")
        self.message_queue.put(None)

        logger.debug("Message queue closed")
        self.mqtt_manager.stop()
        self.mqtt_handler.stop()

        self.stop_event.set()
        logger.debug("Stop event set")
    
        self.pipeline_manager.stop()

        self.pipeline_thread.join()
        logger.debug("Pipeline thread joined")

        self.mqtt_process.join()
        logger.debug("MQTT process joined")

        if self.mqtt_handler_thread:
            self.mqtt_handler_thread.join()
            logger.debug("MQTT handler thread joined")


    def shutdown_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, stopping app")
        self.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', '-c', type=str, default='../config/config.yml')
    args = parser.parse_args()

    app = App(args.config)
    app.start()
