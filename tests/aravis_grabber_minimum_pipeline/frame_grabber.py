import multiprocessing
import gi
import time
from multiprocessing import shared_memory
import numpy as np

import sys

gi.require_version('Aravis', '0.8')
from gi.repository import Aravis


class FrameGrabber:
    def __init__(self, camera_name, shm_name, frame_width = 1920, frame_height = 1080):
        self.camera_name = camera_name
        self.frame_shape = (frame_height, frame_width)
        self.shm_name = shm_name
        self.camera = None
        self.stream = None
        self.frame_size = np.prod(self.frame_shape)
        self.shm = shared_memory.SharedMemory(name=self.shm_name)
        self.frame_buffer = np.ndarray(self.frame_shape, dtype=np.uint8, buffer=self.shm.buf)

        self.last_fps_time = time.time()
        self.fps = 0
        self.buffer_cnt = 0

    def initialize_camera(self):
        # Aravis.enable_interface("Fake")
        Aravis.update_device_list()
        
        print(f"There are {Aravis.get_n_devices()} devices.\n")

        try:
            if self.camera_name:
                self.camera = Aravis.Camera.new(self.camera_name)
            else:
                self.camera = Aravis.Camera.new(None)
        except TypeError:
            print("No camera found")
            exit()

        self.camera.set_region(0, 0, self.frame_shape[1], self.frame_shape[0])
        self.camera.set_frame_rate(54.0)
        self.camera.set_pixel_format_from_string("BayerRG8")

        [x,y,width,height] = self.camera.get_region ()
        payload = self.camera.get_payload ()

        print ("Camera address: %s" %(self.camera_name))
        print ("Camera serial : %s" %(self.camera.get_device_serial_number ()))
        print ("Camera vendor : %s" %(self.camera.get_vendor_name ()))
        print ("Camera model  : %s" %(self.camera.get_model_name ()))
        print ("ROI           : %dx%d at %d,%d" %(width, height, x, y))
        print ("Payload       : %d" %(payload))
        print ("Pixel format  : %s" %(self.camera.get_pixel_format_as_string ()))
        print()
 
        self.stream = self.camera.create_stream(None, None)
        
        for _ in range(10):
            self.stream.push_buffer(Aravis.Buffer.new_allocate(payload))

        self.camera.start_acquisition()

    def grab_frames(self):
        while True:
            buffer = self.stream.pop_buffer()
            if buffer:
                # print(f"Size of buffer:         {sys.getsizeof(buffer)}                 {buffer}")
                # print(f"Size of buffer data:    {sys.getsizeof(buffer.get_data())}")

                data = buffer.get_data()
                self.frame_buffer[:] = np.frombuffer(data, dtype=np.uint8).reshape(self.frame_shape)
                self.stream.push_buffer(buffer)
                self.buffer_cnt += 1

            if time.time() - self.last_fps_time > 1:
                self.fps = self.buffer_cnt / (time.time() - self.last_fps_time)
                self.last_fps_time = time.time()
                self.buffer_cnt = 0
                print(self.fps)
            
            # time.sleep(0.01)

            


    def start(self):
        self.initialize_camera()
        self.grab_frames()
