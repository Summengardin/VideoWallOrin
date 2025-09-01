import json
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
from typing import Optional

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GLib

import logging
logger = logging.getLogger(__name__)

from VisionController.libs.gst.pipeline_manager import PipelineManager
from VisionController.libs.mqtt.mqtt_client import MQTTClient
from VisionController.libs.mqtt.mqtt_helper import load_mqtt_topics
from VisionController.libs.utils import index_dataclass, parse_config, find_digits_in_string
from VisionController.libs.vw_types import Source, SourceType, Camera
from VisionController.libs.factories import CameraFactory

if not Gst.is_initialized():
    Gst.init(None)


class App():

    def __init__(self, config_file):

        self.config_file = config_file
        self.config = parse_config(config_file)
        self.mqtt_config = self.config['mqtt']
        self.pipeline_config = self.config['pipeline']
        self.general_config = self.config['general']
        self.camera_factory = CameraFactory()
        self.camera_factory.load_providers_from_config_file(self.config_file)

        self.command_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        self.topics = load_mqtt_topics(self.mqtt_config)
        self.mqtt_client = MQTTClient(self.mqtt_config.get('broker'), self.mqtt_config.get('port'), self.topics)
        self.mqtt_client.set_on_message_callback(self._cb_mqtt_on_message)


        self.pipeline_manager = PipelineManager(self.pipeline_config)
      

        self.cameras = {}
        self.cameras['Test'] = Camera(id = "Test", ip="test", type="Test", width=1920, height=1080, framerate=60)
        self.cameras['Placeholder'] = Camera(id = "Placeholder", ip="test", type="Test", width=1920, height=1080, framerate=60)

        self.desired_sources = {}

        self._test_zoom_dir = 1

        # Thread references
        self.pipeline_thread = None
        self.handler_thread = None
        self.mqtt_thread = None
        self.monitor_thread = None
        self.monitor_stop_event = None

        # Camera monitoring
        self.monitor_stop_event = threading.Event()
        self.camera_monitor_stop_event = mp.Event()

        self.manager = mp.Manager()
        self.camera_status = self.manager.dict()
        self.camera_uris = self.manager.dict()
        self.disconnect_counters = self.manager.dict()
        self.disconnect_timestamps = self.manager.dict() 
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
        """Stop the application and clean up resources"""
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
            # logger.debug(f"Dequeued:  {topic}: {payload}")

            topic_split = topic.split('/')

            if topic_split[1] == 'VisionControllers':
                if topic_split[2] == 'VisionController0':
                    self._handle_vision_controllers_message(topic_split, payload)
            elif topic_split[1] == 'Cameras':
                logger.debug(f"Handling camera message: {topic}: {payload}")
                self._handle_cameras_message(topic_split, payload)

    def _handle_source_command(self, source_id: int, payload: Optional[str]) -> None:
        """
        Handle `subcommand == "Source"`: assign a camera to a source slot and (re)build the bin.

        - Picks the camera by label (`payload`)
        - If camera is offline/missing, falls back to 'test' placeholder
        - Builds the Gst.Bin using CameraFactory
        - Passes the prebuilt bin to PipelineManager (which links & syncs)
        """
        source_label = (payload or "").strip() or "Placeholder"

        # Create/obtain a source slot object if your structure needs it
        try:
            src_slot = self.pipeline_manager.sources[source_id]
        except (KeyError, IndexError):
            logger.error(f"Invalid source_id {source_id}; no such source slot")
            return

        old_label = src_slot.name
        if old_label == source_label:
            logger.debug(f"Source {source_id} already bound to '{source_label}'; no change")
            return

        logger.debug(f"Source {source_id}: {old_label} → {source_label}")
        src_slot.name = source_label

        self.desired_sources[source_id] = source_label

        # Resolve target camera (or placeholder)
        cam = self.cameras.get(source_label)
        if cam is None:
            logger.warning(f"Camera '{source_label}' not found; using placeholder")
            use_cam = self.cameras.get("Test")
            if use_cam is None:
                logger.error("No placeholder camera 'Test' configured; aborting")
                return
        else:
            self.camera_uris[source_label] = cam.uri

            is_online = self.camera_status.get(cam.id, False)
            use_cam = cam if is_online else self.cameras.get("Test", cam)
            if not is_online:
                logger.debug(f"Camera '{cam.id}' offline → using placeholder for bin build")

        self._add_camera_source(source_id, use_cam)
        logger.debug(f"Adding source {source_id} with camera {use_cam.id} ({use_cam.type})")

        # Update slot metadata (nice to have)
        src_slot.camera = use_cam
        src_slot.type = use_cam.type or "Placeholder"
        src_slot.ip = use_cam.ip or f"Source{source_id}"

        logger.info(f"Source {source_id} now set to camera '{use_cam.id}' (type={use_cam.type})")

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

        if subcommand == 'Source':
            self._handle_source_command(source_id, payload)

        elif subcommand == 'OSD':
            try:
                osd_data = json.loads(payload)
                for osd_key, osd_value in osd_data.items():
                    if isinstance(osd_value, str):
                        osd_value = json.loads(osd_value)
                    
                    if osd_value.get("Type", None) is None:
                        try:
                            self.pipeline_manager.osd_managers[source_id].upsert_text_from_dict(osd_value, osd_key)
                        except Exception as e:
                            logger.error(f"Could not load OSD data: {e}")

                    t = osd_value.get("Type", None)
                    if t is None:
                        continue
                    elif t.lower() == "symbol":
                        self.pipeline_manager.osd_managers[source_id].upsert_symbol_from_dict(osd_value, osd_key)
                    elif t.lower() == "rectangle":  
                        self.pipeline_manager.osd_managers[source_id].upsert_rectangle_from_dict(osd_value, osd_key)
                    elif t.lower() == "text":
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
                control = self.pipeline_manager.sources[source_id].camera.control
                if control is not None:
                    control.continuous_zoom(zoom_speed)
            except Exception as e:
                logger.error(f"Could not initiate continuous zoom for Source {source_id}. \nError: {e}")

        elif subcommand == "PanSpeed":
            try:
                pan_speed = float(payload)
            except TypeError as e:
                logger.error(f"Wrong type provided as pan speed (float expected)\nProvided: {payload}.\nError: {e}")

            try:
                control = self.pipeline_manager.sources[source_id].camera.control
                if control is not None:
                    control.continuous_pan(pan_speed)
            except Exception as e:
                logger.error(f"Could not initiate continuous pan for Source {source_id}. \nError: {e}")
    
        elif subcommand == "TiltSpeed":
            try:
                tilt_speed = float(payload)
            except TypeError as e:
                logger.error(f"Wrong type provided as tilt speed (float expected)\nProvided: {payload}.\nError: {e}")

            try:
                control = self.pipeline_manager.sources[source_id].camera.control
                if control is not None:
                    control.continuous_tilt(tilt_speed)
            except Exception as e:
                logger.error(f"Could not initiate continuous tilt for Source {source_id}. \nError: {e}")

        elif subcommand == "Brightness":
            try:
                brightness = float(payload)
            except TypeError as e:
                logger.error(f"Wrong type provided as brightness (float expected)\nProvided: {payload}.\nError: {e}")

            try:
                control = self.pipeline_manager.sources[source_id].camera.control
                if control is not None:
                    control.set_brightness(brightness)
            except Exception as e:
                logger.error(f"Could not set brightness for Source {source_id}. \nError: {e}")
        else:
            logger.warning(f"Tile-subcommand \"{subcommand}\" not assigned any logic yet")

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

        camera.uri = payload.get('URI', camera.uri)
        parsed = urlparse(camera.uri)

        camera.ip = parsed.hostname
        camera.name = payload.get('DisplayName', camera.name)
        camera.type = payload.get('Type', camera.type)
        camera.control = None
        try:
            camera.control = self.camera_factory.create_camera_control(camera)
        except KeyError as e:
            logger.error(f"Camera type '{camera.type}' not registered in provider registry: {e}")
        except ImportError as e:
            logger.error(f"Failed to import camera control for type '{camera.type}': {e}")
        
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
        """Callback function for MQTT on message. Put the message in the command queue."""
        payload = message.payload.decode('utf-8')
        # payload = message.payload.decode("unicode_escape")
        self.command_queue.put((message.topic, payload))
        # logger.debug(f"Queued:    {message.topic}: {payload}")

    def _check_rtsp_feed(self, uri, timeout_seconds=0.4):
        """Check if an RTSP feed is available using ffprobe."""
        timeout_microseconds = int(timeout_seconds * 1000000)
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-stimeout', f'{timeout_seconds}', '-i', uri,
              '-show_entries', 'stream=codec_type',
              '-of', 'default=noprint_wrappers=1:nokey=1']
        
        if uri == "test":
            return True

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

        self.camera_status['Test'] = True  # Always keep 'test' camera online
        self.camera_status['Placeholder'] = True  # Always keep 'placeholder' camera online

        with ThreadPoolExecutor(max_workers=max(1, n_workers)) as executor:
            while not self.camera_monitor_stop_event.is_set():
                try:
                    # One task per live camera URI
                    futures = {
                        executor.submit(self._check_rtsp_feed, uri): cam_id
                        for cam_id, uri in self.camera_uris.items()
                        if cam_id != "test" and uri
                    }
                    
                    # Collect results; update dict from *this* thread only
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

                    # Periodic debug print
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

        logger.info("Camera monitor process stopped")   

    def _add_placeholder(self, source_id: int) -> bool:
        """Swap a source slot to a placeholder bin."""
        placeholder_cam = self.cameras.get("test")
        try:
            # bin_obj=None => PipelineManager creates its own placeholder (or you can
            # call your placeholder factory here and pass the bin explicitly)
            return self.pipeline_manager.add_source(source_id, bin_obj=None, camera=None)
        except Exception as e:
            logger.error("Failed to add placeholder at slot %s: %s", source_id, e)
            return False


    def _add_camera_source(self, source_id: int, cam) -> bool:
        """Build a provider bin for `cam` and hand it to the pipeline."""
        try:
            bin_obj = self.camera_factory.create_source_bin(source_id, cam)
            # bin_obj = create_source_bin(source_id, cam)
        except Exception as e:
            logger.error(f"Factory failed for {cam.id} ({cam.type}): {e}")
            self._add_placeholder(source_id)
            return False
        
        Gst.debug_bin_to_dot_file(bin_obj, Gst.DebugGraphDetails.ALL, f"source_{source_id}_bin_{cam.type}")

        try:
            return self.pipeline_manager.add_source(source_id, bin_obj=bin_obj, camera=cam)
            # return self.pipeline_manager.add_source_()
        except Exception as e:
            logger.error(f"Pipeline refused bin for slot {source_id} ({cam.id}): {e}")
            return False


    def _monitor_sources(self) -> None:
        """Monitor sources for disconnections and reconnect them using the CameraFactory."""
        # Buffer/counter for missing camera config/URI messages
        missing_cam_log_counters = {}
        missing_cam_log_interval = 25  # Only log every 25 cycles (~5s if 0.2s per cycle)

        while not self.monitor_stop_event.is_set():
            try:
                for source_id, source in enumerate(self.pipeline_manager.sources):
                    desired_cam_id = self.desired_sources.get(source_id)
                    if not desired_cam_id:
                        continue

                    desired_cam = self.cameras.get(desired_cam_id)
                    counter = missing_cam_log_counters.get(desired_cam_id, 0)

                    if desired_cam is None:
                        # If desired camera is not configured, log it and swap to placeholder
                        if counter == 0:
                            logger.error(f"No camera config for {desired_cam_id}")
                        counter = (counter + 1) % missing_cam_log_interval
                        missing_cam_log_counters[desired_cam_id] = counter
                        if source.type not in {"Placeholder", "Test"}:
                            _ = self._add_placeholder(source_id)
                        continue
                
                    elif desired_cam_id in {"Test", "Placeholder"}:
                        continue
                    
                    elif desired_cam.uri is None:

                        if counter == 0:
                            logger.error(f"No URI for {desired_cam_id}")
                        counter = (counter + 1) % missing_cam_log_interval
                        missing_cam_log_counters[desired_cam_id] = counter
                        if source.type not in {"Placeholder", "Test"}:
                            _ = self._add_placeholder(source_id)
                        continue

                    else:
                        counter = 0
                    
                        missing_cam_log_counters[desired_cam_id] = counter


                    # If desired camera is online and the slot is already active for that camera, skip
                    if self.camera_status.get(desired_cam_id, False) and source.active:
                        if source.cam_id == desired_cam_id and source.type not in {"Placeholder", "Test"}:
                            continue  # healthy and already on desired camera

                    # Decide what to feed now
                    cam_is_online = self.camera_status.get(desired_cam_id, False)
                    if cam_is_online:
                        logger.info(f"Camera {desired_cam.ip or desired_cam.id} is online; attempting (re)connect")
                        ok = self._add_camera_source(source_id, desired_cam)
                        if ok:
                            logger.info(f"Slot {source_id} is now connected to {desired_cam.ip or desired_cam.id}")
                            source.cam_id = desired_cam_id
                            source.camera = desired_cam
                            source.type = desired_cam.type
                            source.name = desired_cam.ip or f"Source{source_id}"
                            source.active = True
                        else:
                            logger.error(f"Failed to connect slot {source_id} to {desired_cam.ip or desired_cam.id}; falling back to placeholder")
                            self._add_placeholder(source_id)
                    else:
                        # Camera offline: ensure slot shows placeholder (but don’t thrash if already placeholder/test)
                        if source.type not in {"Placeholder", "Test"} or source.active:
                            logger.debug(f"Camera {desired_cam_id} offline; swapping slot {source_id} to placeholder")
                            self._add_placeholder(source_id)
                            source.type = "Placeholder"
                            source.active = False

                # pacing
                if self.monitor_stop_event.wait(0.2):  # ~5 Hz
                    break

            except Exception as e:
                logger.error("Error in monitor thread: %s", e)
                if self.monitor_stop_event.wait(5.0):
                    break

        logger.info("Monitor thread stopped")
