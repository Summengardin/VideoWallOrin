import threading
import time
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import re
import multiprocessing as mp
import sys
import importlib.util
from urllib.parse import urlparse

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GLib

import logging
logger = logging.getLogger(__name__)

from VisionController.libs.gst.pipeline_manager_ import PipelineManager
from VisionController.libs.mqtt.mqtt_client_ import MQTTClient
from VisionController.libs.mqtt.mqtt_helper import load_mqtt_topics
from VisionController.libs.utils import index_dataclass, parse_config, find_digits_in_string
from VisionController.libs.camera import Camera
from VisionController.libs.vw_types import Source, SourceType


if not Gst.is_initialized():
    Gst.init(None)


class App():

    def __init__(self, config_file):

        self.config_file = config_file
        self.config = parse_config(config_file)
        self.mqtt_config = self.config['mqtt']
        self.pipeline_config = self.config['pipeline']
        self.general_config = self.config['general']
        self.camera_providers = self.config['camera_providers']

        self.command_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        self.topics = load_mqtt_topics(self.mqtt_config)
        self.mqtt_client = MQTTClient(self.mqtt_config.get('broker'), self.mqtt_config.get('port'), self.topics)
        self.mqtt_client.set_on_message_callback(self._cb_mqtt_on_message)


        self.pipeline_manager = PipelineManager(self.pipeline_config)

        # Store camera status using multiprocessing manager
        self.manager = mp.Manager()
        self.camera_status = self.manager.dict()
        self.camera_uris = self.manager.dict()

        self.cameras = {}
        self.cameras['test'] = Camera(id = "Camera0", ip="test", type="Test", width=1920, height=1080, framerate=60)
        self.cameras['test'].provider = self.camera_providers.get(self.cameras['test'].type, None)



        # Store desired source configurations
        self.desired_sources = {}


        self._test_zoom_dir = 1


        # Store thread references
        self.pipeline_thread = None
        self.handler_thread = None
        self.mqtt_thread = None
        self.monitor_thread = None
        self.monitor_stop_event = None

        # Store process references
        self.monitor_stop_event = threading.Event()
        self.camera_monitor_stop_event = mp.Event()  # multiprocessing Event

        # Add disconnect tracking
        self.disconnect_counters = self.manager.dict()  # Track disconnect counts
        self.disconnect_timestamps = self.manager.dict()  # Track when disconnects occur
        self.max_disconnects = 5  # Maximum number of disconnects allowed
        self.disconnect_window = 20  # Time window in seconds (5 minutes)



    def run(self):

        self.pipeline_thread = threading.Thread(target=self.pipeline_manager.start)
        self.pipeline_thread.start()

        time.sleep(1)

        self.handler_thread = threading.Thread(target=self._mqtt_command_handler)
        self.handler_thread.start()

        self.mqtt_thread = threading.Thread(target=self.mqtt_client.start)
        self.mqtt_thread.start()

        self.monitor_thread = threading.Thread(target=self._monitor_sources)
        self.camera_monitor_process = mp.Process(target=self._monitor_cameras_process)
        self.monitor_thread.start()
        self.camera_monitor_process.start()

    def stop(self):
        
        logger.info("Stopping app")
        logger.debug("|--> Stopping monitor threads and process")
        self.camera_monitor_stop_event.set()
        self.monitor_stop_event.set()

        logger.debug("|--> Stopping command queue")
        self.command_queue.put(None)

        logger.debug("|--> Stopping pipeline manager")
        self.pipeline_manager.stop()

        logger.debug("|--> Stopping mqtt client")
        self.mqtt_client.stop()

        logger.debug("|--> Joining monitor threads and process")
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join()
        if self.camera_monitor_process and self.camera_monitor_process.is_alive():
            self.camera_monitor_process.join()
        logger.debug("|--> Joining handler thread")
        if self.handler_thread and self.handler_thread.is_alive():
            self.handler_thread.join()
        
        logger.debug("|--> Joining mqtt thread")
        if self.mqtt_thread and self.mqtt_thread.is_alive():
            self.mqtt_thread.join()
        
        logger.debug("|--> Joining pipeline thread")
        if self.pipeline_thread and self.pipeline_thread.is_alive():
            self.pipeline_thread.join()

        logger.debug("All threads and processes joined")

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
        while not self.pipeline_manager.ready:
            # Hacky solution accessing the internal members of the queue
            with self.command_queue.mutex:
                if None in self.command_queue.queue:
                    return
            time.sleep(0.1)

        while True:
            msg = self.command_queue.get()
            if msg is None:
                break

            topic, payload = msg
            logger.debug(f"Dequeued:  {topic}: {payload}")

            topic_split = topic.split('/')

            if topic_split[1] == 'VisionControllers':
                if topic_split[2] == 'VisionController0':
                    self._handle_vision_controllers_message(topic_split, payload)
            elif topic_split[1] == 'Cameras':
                self._handle_cameras_message(topic_split, payload)
            

    def _handle_vision_controllers_message(self, topic_split, payload):
        command = topic_split[3]
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
        try:
            subcommand = topic_split[4]
        except IndexError:
            subcommand = ""
        # subcommand = ""

        # Tile01 = {"Source":"","Brightness":2.98246E-1,"Zoom":0E0,"OSD":"{\"OSD1\":\"{\\\"text\\\":\\\"\\\",\\\"font_name\\\":\\\"Noto Serif Bold\\\",\\\"font_size\\\":\\\"18\\\",\\\"font_color\\\":\\\"1.0,1.0,1.0,1.0\\\",\\\"bg_color\\\":\\\"0.0,0.0,0.0,0.6\\\",\\\"pos_x\\\":\\\"0\\\",\\\"pos_y\\\":\\\"0\\\",\\\"timeout\\\":\\\"0\\\",\\\"visible\\\":false}\",\"OSD2\":\"{\\\"text\\\":\\\"\\\",\\\"font_name\\\":\\\"…
        # payload = payload.replace("\\\\", "")

        

        # payload = json.loads(payload)
        

        

        

        if subcommand == 'Source':
            source_label = payload

            if source_label is None or source_label == "":
                source_label = "Placeholder"

            # New source?
            if self.pipeline_manager.sources[source_id].cam_id != source_label:
                logger.debug(f"Old source: {self.pipeline_manager.sources[source_id].cam_id}  -->   New source: {source_label}")

                self.desired_sources[source_id] = source_label

                source = self.pipeline_manager.sources[source_id]
                if source is None:
                    source = Source(id=source_id, cam_id=source_label)

                self.pipeline_manager.sources[source_id].cam_id = source_label
                
                # Assign Camera to source
                if self.cameras.get(source_label, None) is not None:
                    self.camera_uris[source.cam_id] = self.cameras[source.cam_id].uri
                    source.camera = self.cameras[source.cam_id] 
                    
                try: # Try add new source to pipeline
                    logger.debug(f"Adding new source")
                    if self.camera_status.get(source.cam_id, False):
                        self.pipeline_manager.add_source(source_id, camera=self.cameras[source.cam_id])
                    else:
                        logger.debug(f"Camera {source.cam_id} is not available, adding placeholder source")
                        self.pipeline_manager.add_source(source_id, camera=self.cameras['test'])
                except KeyError as e:
                    logger.error(f"No camera with that id ({source.cam_id}). Could not find camera: {e}")

                    logger.debug(f"Adding placeholder source")
                    self.pipeline_manager.add_source(source_id, camera=self.cameras['test'])
                except Exception as e:
                    logger.error(f"Could not add source {source_id}. {type(e).__name__}: {e}")
                    logger.debug(f"Adding placeholder source")
                    self.pipeline_manager.add_source(source_id, camera=self.cameras['test'])


                try: # Try get control module for camera
                    source.provider = self.camera_providers.get(source.type, None)

                    if source.provider is not None:
                        module_path = source.provider.get("controller_module_path")
                        module_name = module_path.split("/")[-1].split(".")[0:-1][0]

                        if module_name in sys.modules:
                            control_module = sys.modules[module_name]
                        else:
                            spec = importlib.util.spec_from_file_location(module_name, module_path)
                            control_module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(control_module)
                            sys.modules[module_name] = control_module

                            logger.debug(f"Imported module \"{module_name}\" for type \"{source.type}\", {module_path}") 

                        source.control = control_module.CameraControl(source.camera)

                        print(f"\n\n\nSet source.control to {source.control}")
                    else:
                        logger.info(f"No control provider for camera of type: {source.type}")
                except Exception as e:
                    logger.error(f"Could not import control module for type \"{source.type}\": {e}")
                    
                
                self.pipeline_manager.sources[source_id] = source
        

        elif subcommand == 'OSD':
            try:
                osd_data = json.loads(payload)
                for osd_key, osd_value in osd_data.items():
                    if isinstance(osd_value, str):
                        osd_value = json.loads(osd_value)
                    self.pipeline_manager.osd_managers[source_id].upsert_text_from_dict(osd_value, osd_key)

            except Exception as e:
                logger.error(f"Could not load OSD data: {e}")
                return


        elif subcommand == "ZoomSpeed":
            try:
                zoom_speed = float(payload)
            except TypeError as e:
                logger.error(f"Wrong type provided as zoom speed (float expected)\nProvided: {payload}.\nError: {e}")

            try:
                control = self.pipeline_manager.sources[source_id].control
                control.continuous_zoom(zoom_speed)
            except Exception as e:
                logger.error(f"Could not initiate continuous zoom for Source {source_id}. \nError: {e}")


        elif subcommand == "PanSpeed":
            try:
                pan_speed = float(payload)
            except TypeError as e:
                logger.error(f"Wrong type provided as pan speed (float expected)\nProvided: {payload}.\nError: {e}")

            try:
                control = self.pipeline_manager.sources[source_id].control
                control.continuous_pan(pan_speed)
            except Exception as e:
                logger.error(f"Could not initiate continuous pan for Source {source_id}. \nError: {e}")
    
        elif subcommand == "TiltSpeed":
            try:
                tilt_speed = float(payload)
            except TypeError as e:
                logger.error(f"Wrong type provided as tilt speed (float expected)\nProvided: {payload}.\nError: {e}")

            try:
                control = self.pipeline_manager.sources[source_id].control
                control.continuous_tilt(tilt_speed)
            except Exception as e:
                logger.error(f"Could not initiate continuous tilt for Source {source_id}. \nError: {e}")


        elif subcommand == "Brightness":
            try:
                brightness = float(payload)
            except TypeError as e:
                logger.error(f"Wrong type provided as brightness (float expected)\nProvided: {payload}.\nError: {e}")

            try:
                control = self.pipeline_manager.sources[source_id].control
                control.set_brightness(brightness)
            except Exception as e:
                logger.error(f"Could not set brightness for Source {source_id}. \nError: {e}")



        else:
            logger.warning(f"Tile-subcommand \"{subcommand}\" not assigned any logic yet")

            
            

            # ptz_data = payload.get('PTZ', {})

            # if isinstance(ptz_data, str):
            #     ptz_data = json.loads(ptz_data)

            # pan_speed = ptz_data.get('PanSpeed', 0)
            # tilt_speed = ptz_data.get('TiltSpeed', 0)
            # zoom_speed = ptz_data.get('ZoomSpeed', 0)


            # if source.control is not None:
            #     try:
            #         logger.debug(f"Setting PTZ control: {pan_speed}, {tilt_speed}, {zoom_speed}")
            #         print(f"Setting PTZ control: {pan_speed}, {tilt_speed}, {zoom_speed}")
            #         source.control.ptz.continuous_pantilt(pan_speed=pan_speed*100, tilt_speed=tilt_speed*100)
            #         source.control.continuous_zoom(zoom_speed=zoom_speed)


            #     except Exception as e:
            #         logger.error(f"Could not set PTZ control: {e}")
            # else:
            #     logger.debug(f"No PTZ control for {source.cam_id}")

    
            # osd_data = payload.get('OSD', {})

            # if isinstance(osd_data, str):
            #     # It's a JSON string → decode it
            #     osd_data = json.loads(osd_data)
            # print (f"\n\n\n {osd_key}: {osd_value} \n\n\n")
            # for osd_key, osd_value in osd_data.items():
            #     if osd_key.startswith("OSD"):
            #         # osd = payload.get('OSD')
            #         osd = json.loads(osd_value)
            #         self.pipeline_manager.osd_managers[source_id].upsert_text_from_dict(osd, osd_key)

            
            # source.width = int(payload.get('Width', source.width)) if 'Width' in payload else source.width
            # source.height = int(payload.get('Height', source.height)) if 'Height' in payload else source.height
            # source.framerate = float(payload.get('Framerate', source.framerate)) if 'Framerate' in payload else source.framerate
            # source.format = payload.get('Format', source.format) if 'Format' in payload else source.format

        
        
        # print(self.pipeline_manager.sources)

        # if subcommand == 'Source':
        #     try:
        #         camera_index = find_digits_in_string(payload)
        #     except ValueError:
        #         camera_index = 0
        #     # self.pipeline_manager.sources[source_id].camera = self.pipeline_manager.cameras[camera_index]

        #     self.pipeline_manager.sources[source_id].cam_id = payload
        # elif subcommand == 'Enable':
        #     self.pipeline_manager.sources[source_id].enabled = int(payload) > 0
        #     if int(payload) > 0:
            
        #         try:
        #             bin = self.source_manager.get_source_bin()
        #             cam_id = self.pipeline_manager.sources[source_id].cam_id
                    
        #             success = self._run_with_timeout(self.pipeline_manager.add_source, args=(source_id,), kwargs={'camera': self.cameras[cam_id]})
        #             if not success:
        #                 logger.error(f"Adding source {source_id} timed out")
        #                 success = self._run_with_timeout(self.pipeline_manager.add_source, args=(source_id,))
        #                 if not success:
        #                     logger.error(f"Adding placeholder source {source_id} timed out")
                    

        #             self.pipeline_manager.osd_manager[source_id].upsert_text(f"{self.pipeline_manager.sources[source_id].cam_id} - {self.pipeline_manager.sources[source_id].name}", "upper left", 0, 0, None, 18)
        #             self.pipeline_manager.osd_manager[source_id].upsert_text(f"{self.pipeline_manager.sources[source_id].ip}", "upper right", 1920, 0, 'r', 18)




        #         except Exception as e:
        #             logger.error(f"Could not add source {source_id}. Error: {e}")
        #             success = self._run_with_timeout(self.pipeline_manager.add_source, args=(source_id,))
        #             if not success:
        #                 logger.error(f"Adding placeholder source {source_id} timed out")
                    
        #     else:
        #         try:
        #             success = self._run_with_timeout(self.pipeline_manager.remove_source, args=(source_id,))
        #             if not success:
        #                 logger.error(f"Removing source {source_id} timed out")
        #             success = self._run_with_timeout(self.pipeline_manager.add_source, args=(source_id,))
        #             if not success:
        #                 logger.error(f"Adding placeholder source {source_id} timed out")
        #         except Exception as e:
        #             logger.error(f"Could not stop releasing source {source_id}")

        # elif subcommand == 'Zoom':
        #     value = float(payload)

        #     self._run_with_timeout(self._update_source_feature, args=(source_id, 'zoom'), kwargs={'value': value})
        #     self.pipeline_manager.osd_manager[source_id].upsert_text(f"Zoom: {value:.2f}", "feature", 940, 980, 'c', 36, (1.0, 1.0, 1.0, 1.0), (0, 0, 0, 0.6), 2)
        #     self.pipeline_manager.osd_manager[source_id].upsert_triangle("viewport", 1920//2, 1080//2, 50+600*float(payload), 10, (1.0, 1.0, 1.0, 1.0), -90, 2)


        # elif subcommand == 'Exposure':
        #     value = float(payload)

        #     self._run_with_timeout(self._update_source_feature, args=(source_id, 'exposure_time'), kwargs={'value': value})
        #     self.pipeline_manager.osd_manager[source_id].upsert_text(f"Exposure Time: {value:.2f}", "feature", 940, 980, 'c', 36, (1.0, 1.0, 1.0, 1.0), (0, 0, 0, 0.6), 2)

        # elif subcommand == 'ExposureAuto':
        #     value = int(payload)

        #     self._run_with_timeout(self._update_source_feature, args=(source_id, 'exposure_time_auto'), kwargs={'value': value})
        #     self.pipeline_manager.osd_manager[source_id].upsert_text(f"Exposure Auto: {value}", "feature", 940, 980, 'c', 36, (1.0, 1.0, 1.0, 1.0), (0, 0, 0, 0.6), 2)

        # elif subcommand == 'Gain':
        #     value = float(payload)

        #     self._run_with_timeout(self._update_source_feature, args=(source_id, 'gain'), kwargs={'value': value})
        #     self.pipeline_manager.osd_manager[source_id].upsert_text(f"Gain: {value:.2f}", "feature", 940, 980, 'c', 36, (1.0, 1.0, 1.0, 1.0), (0, 0, 0, 0.6), 2)


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
        cam_id = topic_split[2]
        index = find_digits_in_string(cam_id)
        # command = topic_split[2]

        # VWController/Cameras/Camera00 = {"IP":"10.1.3.71","DisplayName":"Tip","Width":1920,"Height":1080,"Framerate":5.4E1,"Format":"","Type":"","URI":""}
        # index = 0
        # topic_split = ["VWController", "Camera00", "IP"]
        # payload = {"IP":"10.1.3.71","DisplayName":"Tip","Width":1920,"Height":1080,"Framerate":5.4E1,"Format":"","Type":"","URI":""}


        camera = self.cameras.get(cam_id, None)
        
        if camera is None:
            camera = Camera(id=cam_id)
            self.cameras[cam_id] = camera

        payload = json.loads(payload)    

        camera.ip = payload.get('IP', camera.ip)
        camera.uri = payload.get('URI', camera.uri)
        parsed = urlparse(camera.uri)

        camera.ip = parsed.hostname
        camera.name = payload.get('DisplayName', camera.name)
        camera.type = payload.get('Type', camera.type)
        camera.provider = self.camera_providers.get(camera.type, None)
        camera.width = int(payload.get('Width', camera.width))
        camera.height = int(payload.get('Height', camera.height))
        camera.framerate = float(payload.get('Framerate', camera.framerate))
        camera.format = payload.get('Format', camera.format)

        self.cameras[cam_id] = camera

        logger.debug(f"Camera {cam_id} updated: {camera}")

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
            # raise e


    def _cb_mqtt_on_message(self, client, userdata, message):
        payload = message.payload.decode('utf-8')
        self.command_queue.put((message.topic, payload))
        logger.debug(f"Queued:    {message.topic}: {payload}")

    def _check_rtsp_feed(self, uri, timeout_seconds=0.3):
        """Check if an RTSP feed is available using ffprobe."""
        timeout_microseconds = int(timeout_seconds * 1000000)
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-stimeout', f'{timeout_seconds}', '-i', uri,
              '-show_entries', 'stream=codec_type',
              '-of', 'default=noprint_wrappers=1:nokey=1']
        
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True, 
                timeout=timeout_seconds + 0.5, 
                check=True,                  
            )
            return True
        
        except subprocess.CalledProcessError as e:
            # stream was probed but unavailable
            logger.debug(f"RTSP feed check failed for {uri}: {e.stderr.strip()}")
            return False
        except subprocess.TimeoutExpired:
            logger.debug(f"RTSP feed check timed out for {uri} after {timeout_seconds}s")
            return False
        except Exception as e:
            logger.debug(f"Error checking RTSP feed {uri}: {e}")
            return False

    
    def _monitor_cameras_process(self):
        """Runs in its own *process*; reuses a thread-pool instead of creating
        new Thread objects every loop iteration."""

        run_counter = 0
        # size: one worker per real camera (skip 'test' placeholders)
        n_workers = sum(1 for cid, uri in self.camera_uris.items()
                        if cid != "test" and uri)

        # ❶ the pool is born once, lives for the whole method
        with ThreadPoolExecutor(max_workers=max(1, n_workers)) as executor:
            while not self.camera_monitor_stop_event.is_set():
                try:
                    # ❷ schedule one task per live camera URI
                    futures = {
                        executor.submit(self._check_rtsp_feed, uri): cam_id
                        for cam_id, uri in self.camera_uris.items()
                        if cam_id != "test" and uri
                    }

                    # ❸ collect results; update dict from *this* thread only
                    for fut in as_completed(futures):
                        cam_id = futures[fut]
                        try:
                            new_status = bool(fut.result())
                            old_status = self.camera_status.get(cam_id, False)
                            
                            # If camera was connected and now disconnected
                            if old_status and not new_status:
                                current_time = time.time()
                                last_disconnect = self.disconnect_timestamps.get(cam_id, 0)
                                
                                # Reset counter if outside time window
                                if current_time - last_disconnect > self.disconnect_window:
                                    self.disconnect_counters[cam_id] = 1
                                else:
                                    self.disconnect_counters[cam_id] = self.disconnect_counters.get(cam_id, 0) + 1
                                
                                self.disconnect_timestamps[cam_id] = current_time
                                
                                # Check if camera should be discarded
                                if self.disconnect_counters.get(cam_id, 0) >= self.max_disconnects:
                                    logger.warning(f"Camera {cam_id} disconnected too frequently, removing from active cameras")
                                    self.camera_uris[cam_id] = None  # Remove URI to prevent reconnection attempts
                                    self.camera_status[cam_id] = False
                                    continue
                            
                            self.camera_status[cam_id] = new_status
                            
                        except Exception as exc:
                            logger.warning("Camera %s raised %s", cam_id, exc)
                            self.camera_status[cam_id] = False

                    # ❹ periodic debug print
                    run_counter += 1
                    if run_counter >= 10:
                        logger.debug("Camera status: %s", self.camera_status)
                        logger.debug("Disconnect counters: %s", dict(self.disconnect_counters))
                        run_counter = 0

                    # one-second pacing and graceful stop
                    if self.camera_monitor_stop_event.wait(1):
                        break

                except Exception as e:
                    logger.error("Error in camera monitor process: %s", e)
                    # small back-off before retrying
                    if self.camera_monitor_stop_event.wait(5):
                        break

        logger.info("Camera monitor process stopped gracefully")



    def _monitor_sources(self):
        """Monitor sources for disconnections and attempt to reconnect them."""
        while not self.monitor_stop_event.is_set():
            try:
                for source_id, source in enumerate(self.pipeline_manager.sources):
                    desired_cam_id = self.desired_sources.get(source_id, None)                    
                    if desired_cam_id is None:
                        continue

                    current_cam_id = source.cam_id

                    # Skip if current source is alive and is active (not a placeholder)
                    if self.camera_status.get(desired_cam_id, False) and source.active:
                        continue

                    desired_camera = self.cameras.get(desired_cam_id)
                    if desired_camera and desired_camera.uri:
                        # Check if the camera is available using the camera status
                        if self.camera_status.get(desired_cam_id, False):
                            logger.info(f"Camera {desired_camera.ip} is available, attempting to connect")
                            
                            # Remove the current source
                            self.pipeline_manager.remove_source(source_id)
                            
                            try:
                                # Try to add the desired source
                                success = self.pipeline_manager.add_source(source_id, camera=desired_camera)
                                if success:
                                    logger.info(f"Successfully connected source {source_id} to {desired_camera.ip}")
                                else:
                                    logger.error(f"Failed to connect source {source_id} to {desired_camera.ip}")
                                    # Add placeholder if connection failed
                                    self.pipeline_manager.add_source(source_id, camera=self.cameras['test'])
                            except Exception as e:
                                logger.error(f"Error connecting source {source_id}: {e}")
                                # Add placeholder if connection failed
                                self.pipeline_manager.add_source(source_id, camera=self.cameras['test'])
                        else:
                            # logger.debug(f"Camera {desired_camera.ip} is not available")
                            # Only add placeholder if current source is not already a placeholder
                            if source.type != "Placeholder" and source.type != "Test":
                                self.pipeline_manager.remove_source(source_id)
                                self.pipeline_manager.add_source(source_id, camera=self.cameras['test'])
                    else:
                        logger.error(f"No camera configuration or URI found for {desired_cam_id}")
                        # Add placeholder if no camera config found
                        if source.type != "Placeholder" and source.type != "Test":
                            self.pipeline_manager.remove_source(source_id)
                            self.pipeline_manager.add_source(source_id, camera=self.cameras['test'])

                # Sleep for a short interval before next check
                if self.monitor_stop_event.wait(0.2):  # Check every 0.5 seconds
                    break

            except Exception as e:
                logger.error(f"Error in monitor thread: {e}")
                if self.monitor_stop_event.wait(5):  # Sleep before retrying on error
                    break

        logger.info("Monitor thread stopped gracefully")




    