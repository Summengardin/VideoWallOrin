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


from visca_over_ip.camera import Camera as ViscaController
from VisionController.libs.gst.pipeline_manager import PipelineManager
from VisionController.libs.mqtt.mqtt_client_ import MQTTClient
from VisionController.libs.utils import index_dataclass, parse_config, find_digits_in_string
from VisionController.libs.camera import Camera
from VisionController.libs.types import Source, SourceType


Gst.init(None)

seq_step = 0
add_remove = 1

class App():

    def __init__(self, config_file):

        self.config_file = config_file
        self.config = parse_config(config_file)
        self.mqtt_config = self.config['mqtt']
        self.pipeline_config = self.config['pipeline']
        self.general_config = self.config['general']

        self.command_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        self.topics = self._build_mqtt_topics(self.mqtt_config)
        self.mqtt_client = MQTTClient(self.mqtt_config.get('broker'), self.mqtt_config.get('port'), self.topics)
        self.mqtt_client.set_on_message_callback(self._cb_mqtt_on_message)

        self.pipeline_manager = PipelineManager(self.pipeline_config)

        # self.visca = ViscaController("10.1.3.78", self.general_config.get('visca_port'))

        self.cameras = {}
        self.cameras['test'] = Camera(id = "Camera0", ip="test", width=1920, height=1080, framerate=60)

        self._test_zoom_dir = 1


    def run(self):

        pipeline_thread = threading.Thread(target=self.pipeline_manager.start)
        pipeline_thread.start()

        time.sleep(1)


        handler_thread = threading.Thread(target=self._mqtt_command_handler)
        handler_thread.start()
    

        mqtt_thread = threading.Thread(target=self.mqtt_client.start)
        mqtt_thread.start()


        try:
            while True:
                # self._zoom_visca_tester()
                time.sleep(3)  
        except KeyboardInterrupt:
            pass
        
        logger.info("Stopping app")

        logger.debug("|--> Stopping command queue")
        self.command_queue.put(None)

        
        logger.debug("|--> Stopping pipeline manager")
        self.pipeline_manager.stop()

        logger.debug("|--> Stopping mqtt client")
        self.mqtt_client.stop()

        logger.debug("|--> Joining handler thread")
        handler_thread.join()
        
        logger.debug("|--> Joining mqtt thread")
        mqtt_thread.join()
        
        logger.debug("|--> Joining pipeline thread")
        pipeline_thread.join()

        print("Done")


    def _zoom_visca_tester(self):
        try:
            self.visca.zoom(0)
        except:
            print("Failed to stop zoom")
        if self._test_zoom_dir == 1:
            self.visca.zoom_to(1)
            self._test_zoom_dir = 0
        else:
            self.visca.zoom_to(0)
            self._test_zoom_dir = 1


    def _mqtt_command_handler(self):
        while True:
            msg = self.command_queue.get()
            if msg is None:
                break
            topic, payload = msg
            logger.debug(f"Dequeued:  {topic}: {payload}")

            topic_split = topic.split('/')

            if topic_split[0] == 'VisionControllers':
                self._handle_vision_controllers_message(topic_split, payload)
            elif topic_split[0] == 'Cameras':
                self._handle_cameras_message(topic_split, payload)
            

    def _handle_vision_controllers_message(self, topic_split, payload):
        command = topic_split[2]
        if command == 'Fullscreen':
            self.pipeline_manager._set_fullscreen(int(payload))
        elif command in {'Width', 'Height', 'TilerRows', 'TilerColumns'}:
            self._update_pipeline_config(command, payload)
        # elif command == 'StartPipeline' and int(payload) > 0:
        #     self.pipeline_manager.enable_pipeline = True
        #     logger.debug(f"Pipeline enabled: {self.pipeline_manager.enable_pipeline}")
        elif command.startswith('Tile'):
            self._handle_tile_command(command, topic_split, payload)


    def _handle_tile_command(self, command, topic_split, payload): 
        try:
            index = find_digits_in_string(command)
        except ValueError:
            return
        source_id = index - 1
        subcommand = topic_split[3]


        if subcommand == 'Source':
            try:
                camera_index = find_digits_in_string(payload)
            except ValueError:
                camera_index = 0
            # self.pipeline_manager.sources[source_id].camera = self.pipeline_manager.cameras[camera_index]
            self.pipeline_manager.sources[source_id].cam_id = payload
        elif subcommand == 'Enable':
            self.pipeline_manager.sources[source_id].enabled = int(payload) > 0
            if int(payload) > 0:
            
                try:
                    cam_id = self.pipeline_manager.sources[source_id].cam_id
                    
                    success = self._run_with_timeout(self.pipeline_manager.add_source, args=(source_id,), kwargs={'camera': self.cameras[cam_id]})
                    if not success:
                        logger.error(f"Adding source {source_id} timed out")
                        success = self._run_with_timeout(self.pipeline_manager.add_source, args=(source_id,))
                        if not success:
                            logger.error(f"Adding placeholder source {source_id} timed out")
                except Exception as e:
                    logger.error(f"Could not add source {source_id}. Error: {e}")
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

        elif subcommand == 'Zoom':
            self._run_with_timeout(self._update_source_feature, args=(source_id, 'zoom'), kwargs={'value': float(payload)})
            self.pipeline_manager.osd_manager[source_id].upsert_text(f"Zoom: {payload}", "feature", 940, 980, 36, (1.0, 1.0, 1.0, 1.0), (0, 0, 0, 0.6), 5)
            self.pipeline_manager.osd_manager[source_id].upsert_triangle("viewport", 1920//2, 1080//2, 50+500*float(payload), 10, (1.0, 1.0, 1.0, 1.0), -90, 5)


        elif subcommand == 'Exposure':
            self._run_with_timeout(self._update_source_feature, args=(source_id, 'exposure_time'), kwargs={'value': float(payload)})
            self.pipeline_manager.osd_manager[source_id].upsert_text(f"Exposure Time: {payload}", "feature", 940, 980, 36, (1.0, 1.0, 1.0, 1.0), (0, 0, 0, 0.6), 5)

        elif subcommand == 'ExposureAuto':
            self._run_with_timeout(self._update_source_feature, args=(source_id, 'exposure_time_auto'), kwargs={'value': int(payload)})
            self.pipeline_manager.osd_manager[source_id].upsert_text(f"Exposure Auto: {payload}", "feature", 940, 980, 36, (1.0, 1.0, 1.0, 1.0), (0, 0, 0, 0.6), 5)

        elif subcommand == 'Gain':
            self._run_with_timeout(self._update_source_feature, args=(source_id, 'gain'), kwargs={'value': float(payload)})
            self.pipeline_manager.osd_manager[source_id].upsert_text(f"Gain: {payload}", "feature", 940, 980, 36, (1.0, 1.0, 1.0, 1.0), (0, 0, 0, 0.6), 5)


    def _update_source_feature(self, source_id: int, feature, value):
        source = self.pipeline_manager.sources[source_id]

        if source.type == SourceType.BAYER:
            if feature == "exposure_time_auto":
                
                source.camera.exposure_time_auto = 'Off' if value == 0 else 'Continuous'
                return self.pipeline_manager.set_exposure_auto_source(source.id, source.camera.exposure_time_auto)

            elif feature == "exposure_time":
                source.camera.exposure_time = value
                if source.camera.exposure_time_auto != 'Off':
                    return self.pipeline_manager.set_target_brightness_source(source.id, source.camera.exposure_time)
                
                return self.pipeline_manager.set_exposure_time_source(source.id, source.camera.exposure_time) 
                
            elif feature == "gain":
                source.camera.gain = value
                if source.camera.exposure_time_auto != 'Off':
                    return 
                return self.pipeline_manager.set_gain_source(source.id, source.camera.gain)                

            elif feature == "zoom" and source.camera.has_zoom:
                source.camera.zoom = value
                return self.pipeline_manager.set_zoom_source(source.id, source.camera.zoom)

        if source.type == SourceType.RTSP and source.camera.visca_controller is not None:

            if feature == "exposure_time_auto":
                source.camera.exposure_time_auto = 'auto' if value == 1 else 'manual'
                try:
                    if value == 1: 
                        source.camera.visca_controller.set_exposure_compensation_on()
                    else: 
                        source.camera.visca_controller.set_exposure_compensation_off()

                    source.camera.visca_controller.autoexposure_mode(source.camera.exposure_time_auto)


                except Exception as e:
                    logger.warning(f"Camera {source.camera.ip}: Failed to set exposure time auto: {e}")

            elif feature == "exposure_time":
                try:
                    if source.camera.exposure_time_auto == 'manual':
                        value = int((1 - value) * 21)
                        source.camera.exposure_time = value
                        source.camera.visca_controller.set_shutter(value)
                    else:
                        value = int(value * 14)
                        source.camera.visca_controller.set_exposure_compensation(value)
                except Exception as e:
                    logger.warning(f"Camera {source.camera.ip}: Failed to set exposure time: {e}")
                    
            elif feature == "gain":
                value = int(value * 14 + 1)
                source.camera.gain = value
                try:
                    source.camera.visca_controller.set_gain(value)
                except Exception as e:
                    logger.warning(f"Camera {source.camera.ip}: Failed to set gain: {e}")

            elif feature == "zoom":
                source.camera.zoom = value
                try:
                    source.camera.visca_controller.zoom_to(value)
                except Exception as e:
                    logger.warning(f"Camera {source.camera.ip}: Failed to set zoom: {e}")
            else:
                return False

            return True


    def _handle_cameras_message(self, topic_split, payload):
        index = find_digits_in_string(topic_split[1])
        cam_id = topic_split[1]
        command = topic_split[2]

        camera = self.cameras.get(cam_id, None)
        if camera is None:
            camera = Camera(id=cam_id)
            self.cameras[cam_id] = camera

        if command == 'IP':
            camera.ip = payload
        elif command == 'Type':
            camera.type = payload
            camera.has_zoom = payload != 'Basler'

            if camera.type == "Compressed":
                self._run_with_timeout(camera.set_controller, args=(ViscaController(camera.ip, 1000),))
        elif command == 'Name':
            camera.name = payload
        elif command == 'Width':
            camera.width = int(payload)
        elif command == 'Height':
            camera.height = int(payload)
        elif command == 'Format':
            camera.format = payload
        elif command == 'Framerate':
            camera.framerate = float(payload)


        # self._run_with_timeout(self.pipeline_manager.update_camera_features, args=(camera.ip,))



    def _update_pipeline_config(self, command, payload):
        if command == 'Width':              
            self.pipeline_manager.width = int(payload)
        elif command == 'Height':           
            self.pipeline_manager.height = int(payload)
        elif command == 'TilerRows':        
            self.pipeline_manager.tiler_rows = int(payload)
        elif command == 'TilerColumns':    
            self.pipeline_manager.tiler_columns = int(payload)


    def _run_with_timeout(self, func, args=(), kwargs={}, timeout=30):
        """Runs a function asynchronously with a timeout."""
        logger.debug(f"Running {func.__name__} with timeout {timeout}")
        future = self.executor.submit(func, *args, **kwargs)

        try:
            result = future.result(timeout=timeout)
            return result
        except TimeoutError:
            logger.error(f"Function {func.__name__} timed out")
            return False
        except Exception as e:
            logger.error(f"Function {func.__name__} raised an exception: {e}")
            # raise e


    def _cb_mqtt_on_message(self, client, userdata, message):
        payload = message.payload.decode('utf-8')
        self.command_queue.put((message.topic, payload))
        logger.debug(f"Queued:    {message.topic}: {payload}")


    def _build_mqtt_topics(self, mqtt_config):
        cameras = mqtt_config.get('cameras')
        camera_subtopics = mqtt_config.get('camera_subtopics')
        vision_controllers = mqtt_config.get('vision_controllers')
        vision_controller_subtopics = mqtt_config.get('vision_controller_subtopics')
        tile_subtopics = mqtt_config.get('tile_subtopics')

        topics = []
        for camera in cameras:
            for subtopic in camera_subtopics:
                if type(subtopic) is dict:
                    topic = subtopic.keys()[0]
                    qos = subtopic.values()[0]
                    topics.append((f"Cameras/{camera}/{topic}", qos))
                else:
                    topics.append((f"Cameras/{camera}/{subtopic}", 0))

        for vision_controller in vision_controllers:
            for subtopic in vision_controller_subtopics:  
                if isinstance(subtopic, dict):
                    topic = list(subtopic.keys())[0]
                    qos = subtopic[topic]
                    topics.append((f"VisionControllers/{vision_controller}/{topic}", qos))
                else:
                    topics.append((f"VisionControllers/{vision_controller}/{subtopic}", 0))

            for tile_id in ['01', '02', '03', '04']:
                    for subtopic in tile_subtopics:
                        topics.append((f"VisionControllers/{vision_controller}/Tile{tile_id}/{subtopic}", 0))

        return topics





    