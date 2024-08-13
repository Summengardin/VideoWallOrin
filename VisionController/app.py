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
from VisionController.libs.gst.pipeline_manager import PipelineManager, Source, SourceType
from VisionController.libs.mqtt.mqtt_client_ import MQTTClient
from VisionController.libs.utils import index_dataclass, parse_config, find_digits_in_string
from VisionController.libs.camera import Camera


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
        
        self.topics = self._build_topics(self.mqtt_config.get('cameras'), self.mqtt_config.get('camera_subtopics'), self.mqtt_config.get('vision_controllers'), self.mqtt_config.get('vision_controller_subtopics'))
        self.mqtt_client = MQTTClient(self.mqtt_config['broker'], self.mqtt_config['port'], self.topics)
        self.mqtt_client.set_on_message_callback(self._mqtt_on_message)

        self.pipeline_manager = PipelineManager(self.pipeline_config)

        # self.visca = ViscaController("10.1.3.78", self.general_config.get('visca_port'))

        self.cameras = {}
        self.cameras['Camera0'] = Camera(id = "Camera0", ip="test", width=1920, height=1080, framerate=60)

        self._test_zoom_dir = 1



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
                # self._zoom_visca_tester()
                time.sleep(3)  
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
        try:
            index = find_digits_in_string(command)
        except ValueError:
            return
        source_id = index - 1
        subcommand = topic_split[3]

        if index is not None:
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


    def _update_pipeline_config(self, command, payload):
        if command == 'Width':              
            self.pipeline_manager.width = int(payload)
        elif command == 'Height':           
            self.pipeline_manager.height = int(payload)
        elif command == 'TilerRows':        
            self.pipeline_manager.tiler_rows = int(payload)
        elif command == 'TilerColumns':    
            self.pipeline_manager.tiler_columns = int(payload)


    def _handle_cam_objects_message(self, topic_split, payload):
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
                camera.set_controller(ViscaController(camera.ip, 1000))

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
            self._run_with_timeout(self._update_camera_setting, args=(camera, "zoom", camera.zoom))
        elif command == 'Exposure':
            camera.exposure_time = float(payload)
            self._run_with_timeout(self._update_camera_setting, args=(camera, "exposure_time", camera.exposure_time))
        elif command == 'ExposureAuto':
            camera.exposure_time_auto = int(payload)
            self._run_with_timeout(self._update_camera_setting, args=(camera, "exposure_time_auto", camera.exposure_time_auto))
        elif command == 'Gain':
            camera.gain = float(payload)
            self._run_with_timeout(self._update_camera_setting, args=(camera, "gain", camera.gain))
        elif command == 'GainAuto':
            camera.gain_auto = int(payload)
            self._run_with_timeout(self._update_camera_setting, args=(camera, "gain_auto", camera.gain_auto))

        # self._run_with_timeout(self.pipeline_manager.update_camera_features, args=(camera.ip,))


    def _update_camera_setting(self, camera: Camera, setting: str, value):

        if camera.type == "Basler" or camera.type == "TheImagingSource":
            setting_dict = {}
            if setting == "exposure_time_auto":
                camera.exposure_time_auto = 'Off' if value == 0 else 'Continuous'
                camera.gain_auto = 'Off' if value == 0 else 'Continuous'
                setting_dict = {"ExposureAuto": camera.exposure_time_auto,
                                "GainAuto": camera.gain_auto,
                                "AutoFunctionROISelector": "ROI1",
                                "AutoFunctionROIUseBrightness": True}
                
            elif setting == "exposure_time":
                camera.exposure_time = value
                if camera.exposure_time_auto == 'Off':
                    setting_dict = {"ExposureTime": camera.exposure_time}
                else:
                    if camera.type == "TheImagingSource":
                        setting_dict = {"ExposureAutoReference": int(camera.exposure_time/20000 * 255)}
                    else:
                        setting_dict = {"AutoTargetBrightness": camera.exposure_time/20000}
                
            elif setting == "gain":
                camera.gain = value
                setting_dict = {"Gain": camera.gain}

            elif setting == "gain_auto":
                camera.gain_auto = 'Off' if value == 0 else 'Continuous'
                # setting_dict = {"GainAuto": camera.gain_auto}

            elif setting == "zoom":
                camera.zoom = value
                setting_dict = {"Zoom": camera.zoom}

            elif setting == "zoom" and camera.has_zoom:
                setting_dict["Zoom"] = camera.zoom 

            return self.pipeline_manager.update_camera_feature(camera.ip, setting_dict)


        elif camera.type == "Compressed" and camera.visca_controller is not None:

            if setting == "exposure_time_auto":
                if value == 0:
                    # MANUAL
                    value = 3
                    camera.visca_controller.set_exposure_compensation_off()
                elif value == 1:
                    # AUTO
                    value = 0
                    camera.visca_controller.set_exposure_compensation_on()
                camera.exposure_time_auto = value
                modes = {0: "auto", 1: "iris priority", 2: "shutter priority", 3: "manual"}
                camera.visca_controller.autoexposure_mode(modes[value])

            elif setting == "exposure_time":
                try:
                    if camera.exposure_time_auto == 3:
                        value = int((20000-value)/20000 * 21)
                        camera.exposure_time = value
                        camera.visca_controller.set_shutter(value)
                    else:
                        value = int(value/20000 * 14)
                        camera.visca_controller.set_exposure_compensation(value)
                except Exception as e:
                    logger.error(f"Failed to set exposure time: {e}")
                    
            elif setting == "gain":
                value = int(value/100 * 14 + 1)
                self.gain = value
                try:
                    camera.visca_controller.set_gain(value)
                except:
                    pass

            elif setting == "zoom":
                value = value/1000 # percent
                self.zoom = value
                try:
                    camera.visca_controller.zoom_to(value)
                except:
                    pass
            else:
                return False

            return True


    def _run_with_timeout(self, func, args=(), kwargs={}, timeout=5):
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
            raise e


    def _update_camera_features(self, source: Source):
        if source.bin is None or source.camera is None:
            print("Camera or bin is None")
            return
        
        if source.camera.type == SourceType.BAYER:
            src = source.bin.get_by_name(f"source-{source.ip}")
            if src is None:
                return

            self._update_camera_features_aravis(src)

        elif source.camera.type == SourceType.RTSP:
            ip = source.camera.ip
            self._update_camera_features_rtsp(ip)


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





    