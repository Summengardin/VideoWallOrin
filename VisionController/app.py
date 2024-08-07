import threading
import time
import queue
from concurrent.futures import ThreadPoolExecutor

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GLib

import logging
logger = logging.getLogger(__name__)


from .libs.gst.pipeline_manager import PipelineManager
from .libs.types import SourceType, Source, Camera
from .libs.mqtt.mqtt_client_ import MQTTClient
from .libs.utils import index_dataclass, parse_config, find_digits_in_string

Gst.init(None)

seq_step = 0
add_remove = 1

Cameras = [Camera(ip="10.1.3.74", type="Basler", width=1920, height=1080, format="BayerRG8", framerate=60), Camera(ip="10.1.3.79", type="TheImagingSource", width=1920, height=1080, format="BayerRG8", framerate=54)]


class App():

    def __init__(self, config_file):

        self.config_file = config_file
        self.config = parse_config(config_file)
        self.mqtt_config = self.config['mqtt']
        self.pipeline_config = self.config['pipeline']

        self.command_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        self.topics = self._build_topics(self.mqtt_config.get('cameras'), self.mqtt_config.get('camera_subtopics'), self.mqtt_config.get('vision_controllers'), self.mqtt_config.get('vision_controller_subtopics'))
        self.mqtt_client = MQTTClient(self.mqtt_config['broker'], self.mqtt_config['port'], self.topics)
        self.mqtt_client.set_on_message_callback(self._mqtt_on_message)

        self.pipeline_manager = PipelineManager(self.pipeline_config)


    def run(self):

        pipeline_thread = threading.Thread(target=self.pipeline_manager.start)
        pipeline_thread.start()

        time.sleep(1)


        handler_thread = threading.Thread(target=self._command_handler)
        handler_thread.start()
    

        mqtt_thread = threading.Thread(target=self.mqtt_client.start)
        mqtt_thread.start()


        try:
            while True:
                time.sleep(1)  
        except KeyboardInterrupt:
            pass
        finally:
            self.command_queue.put(None)
        
        self.pipeline_manager.stop()
        self.mqtt_client.stop()

        handler_thread.join()
        mqtt_thread.join()
        pipeline_thread.join()

        print("Done")


    def _command_handler(self):
        while True:
            msg = self.command_queue.get()
            if msg is None:
                break
            topic, payload = msg
            logger.debug(f"Dequeued:  {topic}: {payload}")

            topic_split = topic.split('/')

            if topic_split[0] == 'VisionControllers':
                self._handle_vision_controllers_message(topic_split, payload)
            elif topic_split[0] == 'CamObjects':
                self._handle_cam_objects_message(topic_split, payload)
            

    def _handle_vision_controllers_message(self, topic_split, payload):
        command = topic_split[2]
        if command == 'Fullscreen':
            self.pipeline_manager.toggle_fullscreen(int(payload))
        elif command in {'Width', 'Height', 'TilerRows', 'TilerColumns'}:
            self._update_pipeline_config(command, payload)
        # elif command == 'StartPipeline' and int(payload) > 0:
        #     self.pipeline_manager.enable_pipeline = True
        #     logger.debug(f"Pipeline enabled: {self.pipeline_manager.enable_pipeline}")
        elif command.startswith('Tile'):
            self._handle_tile_command(command, topic_split, payload)




    def _handle_tile_command(self, command, topic_split, payload):
        index = find_digits_in_string(command)
        source_id = index - 1
        subcommand = topic_split[3]

        if index is not None:
            if subcommand == 'Source':
                camera_index = find_digits_in_string(payload)
                self.pipeline_manager.sources[source_id].camera = self.pipeline_manager.cameras[camera_index]
            elif subcommand == 'Enable':
                self.pipeline_manager.sources[source_id].enabled = int(payload) > 0
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


    def _update_pipeline_config(self, command, payload):
        if command == 'Width':              self.pipeline_manager.width         = int(payload)
        elif command == 'Height':           self.pipeline_manager.height        = int(payload)
        elif command == 'TilerRows':        self.pipeline_manager.tiler_rows    = int(payload)
        elif command == 'TilerColumns':     self.pipeline_manager.tiler_columns = int(payload)


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

        self._run_with_timeout(self.pipeline_manager.update_camera_features, args=(camera.ip,))

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


    def _mqtt_on_message(self, client, userdata, message):
        payload = message.payload.decode('utf-8')
        self.command_queue.put((message.topic, payload))
        logger.debug(f"Queued:    {message.topic}: {payload}")


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





    