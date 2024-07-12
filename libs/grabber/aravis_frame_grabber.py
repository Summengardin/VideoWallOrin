
import os
import time
import multiprocessing
import multiprocessing.sharedctypes
import numpy as np
import typing
import signal
import ctypes

import cv2

import gi
gi.require_version('Aravis', '0.8')
from gi.repository import Aravis, GLib

H, W, D = 1080, 1920, 1
IMAGE_FORMAT = "BayerRG8"
#IMAGE_FORMAT = "YUV422_YUYV_Packed"

CAM_GRABBER_PROCESS_SILENT = False
NO_CAM_COUNTER_MAX = 5
FPS_PRINT_INTERVAL = 10 # seconds


class CamGrabber():
    def __init__(self, ip_address: str = None, H = H, W = W, D = D) -> None:
        self.cam_grabber_process = CamGrabberProcess(ip_address, H, W, D)
        self.last_frame = None
        
        self.last_new_frame_time = time.time()
        self.max_frame_time = 2 #s
        
        self.p = multiprocessing.Process(target=self.cam_grabber_process.run, args=())
        self.p.daemon = CAM_GRABBER_PROCESS_SILENT
        self.p.start()
        
        self.H = H
        self.W = W
        self.D = D
        #self.D = 4 # BGRX test
 
 
    def get_frame(self):      
        with self.cam_grabber_process.lock:
            now = time.time()
            if self.cam_grabber_process.new_frame_available.value:
                self.last_new_frame_time = now
                self.cam_grabber_process.new_frame_available.value = 0
                            
                self.last_frame = np.asarray(self.cam_grabber_process.frame_arr).reshape(self.H,self.W,self.D)

                return self.last_frame
            else:
                if (now - self.last_new_frame_time > self.max_frame_time):
                    return None
                return self.last_frame
            

    def get_frame_with_timestamp(self):
        frame = self.get_frame()
        with self.cam_grabber_process.lock:
            return frame, self.cam_grabber_process.last_frame_time.value

  
    def is_connected(self) -> bool:
        return self.cam_grabber_process.is_connected.value
    
    
    def is_active(self) -> bool:
        return True
        return self.cam_grabber_process.is_running.value
    
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
        
    def stop(self):
        self.p.terminate()
        self.p.join()
        print("CamGrabber has been deleted")
    
    def __del__(self):
        if self.p.is_alive():
            self.p.terminate()
            
        try:
            self.p.join()
        except:
            pass

        
class CamGrabberProcess():
    def __init__(self, ip_address: str, H=H, W=W, D=D) -> None:
        self.ip_address = ip_address
        self.H = H
        self.W = W
        self.D = D
        
        self.last_frame_time = multiprocessing.Value('d', 0.0)
        self.frame_arr = multiprocessing.sharedctypes.RawArray(ctypes.c_uint8, self.H*self.W*self.D)
        self.lock = multiprocessing.Lock()
        self.new_frame_available = multiprocessing.Value('i', 0)
    
        self.camera = None
        self.stream = None
        self.no_cam_counter = 0
        self.fps_counter = 0
        self.last_fps_print_time = 0
        self.cancel = False
        self.active = False
        
        self.is_running = multiprocessing.Value(ctypes.c_bool, 0)
        self.is_connected = multiprocessing.Value(ctypes.c_bool, 0)


    def run_(self):
        print("-- Starting CamGrabberProcess --")
        self.is_running.value = True
        

        has_cam = False
        
        try:
            

            if self.no_cam_counter > NO_CAM_COUNTER_MAX:
                self.no_cam_counter = 0
                print(f"NO_CAM_COUNTER exceeded {NO_CAM_COUNTER_MAX}")
                has_cam = False
                time.sleep(5)
                #self.is_running.value = False
                #continue
                
            if not has_cam:
                has_cam = self.__find_cam()
            
            if has_cam:
                self.__start_grabber()

                
        except KeyboardInterrupt:
            print("CamGrabberProcess interrupted by KeyboardInterrupt")
        except Exception as e:
            print(f"CamGrabberProcess crashed ({type(e).__name__}): {e}")
               
        self.is_running.value = False    
        if self.camera:
            self.camera.stop_acquisition()  
        
    def run(self):
        self.is_running.value = True

        print("===== Finding camera =====")
        Aravis.update_device_list()

        self.camera = Aravis.Camera.new(self.ip_address)

        print("===== Configuring camera =====")
        self.camera.set_pixel_format_from_string(IMAGE_FORMAT)
        print(f"Using pixel format: {self.camera.get_pixel_format_as_string()}")

        self.camera.set_region(0, 0, self.W, self.H)
        self.camera.set_frame_rate(50)

        print("===== Starting camera =====")

        stream = self.camera.create_stream(None, None)
        for _ in range(1):
            stream.push_buffer(Aravis.Buffer.new(self.camera.get_payload()))

        self.camera.start_acquisition()
        

        while True:
            if not self.is_running.value:
                break
            buffer = stream.pop_buffer()
            if buffer:
                if buffer.get_status() == Aravis.BufferStatus.SUCCESS:
                    data = buffer.get_data()

                    with self.lock:
                        self.new_frame_available.value = 1
                        ctypes.memmove(self.frame_arr, data, self.frame_arr._length_)
                
                stream.push_buffer(buffer)

        self.camera.stop_acquisition()


    def __find_cam(self):
        has_cam = False
        
        print("\n-- Searching for camera --")
        
        try:
            Aravis.update_device_list()
        except Exception as e: 
            print(f"Error when updating device list: {e}")
                
        print(f"There are {Aravis.get_n_interfaces()} interfaces")
        for i in range(Aravis.get_n_interfaces()):
            print(f"Interface {i}: {Aravis.get_interface_id(i)}")       
        print()
        

        n_devices = Aravis.get_n_devices()
        if n_devices == 0:
            print(f"[ERROR] Could not find any devices")
            self.no_cam_counter += 1
            time.sleep(3)
        else:
            print(f"Found {n_devices} cameras:")
            print("IP, ID, Model, Serial number, Physical ID, Protocol")
            for i in range (n_devices):
                print(f"    - {Aravis.get_device_address(i)}, {Aravis.get_device_id(i)}, {Aravis.get_device_model(i)}, {Aravis.get_device_serial_nbr(i)}, {Aravis.get_device_physical_id(i)}, {Aravis.get_device_protocol(i)}")
            print()

            #print(f"\nConnecting to camera: {serial_number}")
            if n_devices > 1:
                print("Found multiple cameras, using first one")
            print(f"Connecting to camera: {Aravis.get_device_address(1)}")
            
            try:
                print("Creating camera object")
                #camera = self.h.create({"serial_number":serial_number}) # type:ignore
                self.camera = Aravis.Camera.new(Aravis.get_device_address(1))
                print("Camera object created")
            except Exception as e:
                print(f"Exception when creating camera: {e}")
         
            try:
                self.__configure_camera()
            except Exception as e:
                print("Exception when configuring camera: ",e)

            print(f"===== Connected to Camera: {self.camera.get_vendor_name()} - {self.camera.get_model_name()} - {self.camera.get_device_id()} =====\n")
            
            has_cam = True

        return has_cam
  
        
    def __configure_camera(self):
        print("\n-- Configuring camera --")
        self.camera.set_pixel_format_from_string("RGB8")
        print(f"Using pixel format: {self.camera.get_pixel_format_as_string()}")

        self.camera.set_region(0, 0, 1920, 1080)
        self.camera.set_frame_rate(30.0)



    def __start_grabber(self):
        print("-- Starting acquisition --")
        self.active = True
        
        payload = self.camera.get_payload()
        self.stream = self.camera.create_stream(None, None)
        
        if self.stream is None:
            print("Could not create stream")
            return

        for _ in range(1):
            self.stream.push_buffer(Aravis.Buffer.new(payload))
        
        self.camera.start_acquisition()


        self.stream.connect("new-buffer", self.__new_buffer_cb)
        self.stream.set_emit_signals(True)

        self.camera.get_device().connect("control-lost", self.control_lost_cb)

        GLib.timeout_add_seconds(1, self.periodic_task_cb)

        self.main_loop = GLib.MainLoop()

        signal.signal(signal.SIGINT, self.cancel)

        self.main_loop.run()

        self.camera.stop_acquisition()
        self.stream.set_emit_signals(False)

        self.stream = None
        self.camera = None


    def __new_buffer_cb(self, stream):
        buffer = stream.try_pop_buffer()
        
        if buffer and buffer.get_status() == Aravis.BufferStatus.SUCCESS:
            
            try:
                frame = self.__retrieve_img_from_buffer(buffer)

                if frame is not None:

                    with self.lock:

                        self.last_frame_time.value = time.time()
                        print("New buffer")
                        self.fps_counter += 1
                        self.new_frame_available.value = 1

                        ctypes.memmove(self.frame_arr, frame.ctypes.data, self.frame_arr._length_)


            except Exception as e:
                print("Exception when retrieving frame: ",e)

            stream.push_buffer(buffer)


    def control_lost_cb(self, device):
        print("Control lost")
        self.cancel = True


    def periodic_task_cb(self):
        print(f"Frame rate = {self.fps_counter} FPS")
        self.fps_counter = 0

        if self.cancel:
            self.main_loop.quit()
            return False

        return True
    

    def __retrieve_img_from_buffer(self, buffer: Aravis.Buffer):
        frame_buffer = buffer.get_data()
        try:
            frame = np.frombuffer(frame_buffer, dtype=np.uint8).reshape((self.W, self.H, self.D))
        except ValueError:
            print("Frame is not valid")
            return None
        
        if IMAGE_FORMAT == "Mono8":
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        elif IMAGE_FORMAT == "BayerBG8" or IMAGE_FORMAT == "BayerBG10p" or IMAGE_FORMAT == "BayerBG10":
            frame = cv2.cvtColor(frame, cv2.COLOR_BayerRG2BGR)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA) 
        elif IMAGE_FORMAT == "YUV422_8" or IMAGE_FORMAT == "YUV422_YUYV_Packed":
            frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_YUYV) 

        return frame
     

    def __del__(self):
        self.running = False
        print("CamGrabberProcess has been deleted")
        

if __name__== "__main__":
    with CamGrabber() as grabber:
        #cv2.namedWindow("Window", cv2.WINDOW_NORMAL)
        cv2.namedWindow("Window", cv2.WINDOW_KEEPRATIO | cv2.WINDOW_FULLSCREEN)
        #cv2.setWindowProperty("Window", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        #time.sleep(3)
        while grabber.is_active():
            frame = grabber.get_frame()
            
            
            # Convert the Bayer image to BGR format using OpenCV
            if frame is not None:
                frame = frame.reshape((H, W))
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BAYER_RG2RGB)

                
                # Display the image
                cv2.imshow('Bayer Image', frame_bgr)

                # Exit the loop when 'q' is pressed
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        
        cv2.destroyAllWindows()
        print("Exiting main")
    
       