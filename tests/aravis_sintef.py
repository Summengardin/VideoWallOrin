import time
import logging
import numpy as np
import ctypes
import gi
import threading
import multiprocessing as mp

gi.require_version('Aravis', '0.8')
from gi.repository import Aravis
import cv2


ips = { '10.1.3.75': 'tis',
        '10.1.3.76': 'basler',
        '10.1.3.77': 'basler'}

# ips = { '10.1.3.76': 'basler'}


class AravisException(Exception):
    pass

class Camera:
    """
    Create a Camera object. 
    name is the camera ID in aravis.
    If name is None, the first found camera is used.
    If no camera is found an AravisException is raised.
    """
    def __init__(self, name=None, loglevel=logging.WARNING):
        self.logger = logging.getLogger(self.__class__.__name__)
        if len(logging.root.handlers) == 0: #dirty hack
            logging.basicConfig()
        self.logger.setLevel(loglevel)
        self.name = name
        try:
            self.cam = Aravis.Camera.new(name)
        except TypeError:
            if name:
                raise AravisException(f"Error the camera {name} was not found")
            else:
                raise AravisException("Error no camera found")
        self.name = self.cam.get_model_name()
        self.logger.info("Camera object created for device: %s", self.name)
        self.dev = self.cam.get_device()
        self.stream = self.cam.create_stream(None, None)
        if self.stream is None:
            raise AravisException("Error creating buffer")
        self._frame = None
        self._last_payload = 0
        self._last_frame_time = 0

    def __getattr__(self, name):
        if hasattr(self.cam, name): # expose methods from the aravis camera object which is also relatively high level
            return getattr(self.cam, name)
        else:
            raise AttributeError(name)

    def __dir__(self):
        tmp = list(self.__dict__.keys()) + dir(self.cam)
        return tmp

    def load_config(self, path):
        """
        read a config file as written by stemmer imaging for example
        and apply the config to the camera
        """
        with open(path) as f:
            for line in f:
                if line.startswith("#"):
                    continue
                else:
                    name, val = line.split()
                    name = name.strip()
                    val = val.strip()
                    self.logger.info("Config file: Setting %s to %s ", name, val)
                    try:
                        self.set_feature(name, val)
                    except AravisException as ex:
                        self.logger.warning(ex)

    def get_feature_type(self, name):
        genicam = self.dev.get_genicam()
        node = genicam.get_node(name)
        if not node:
            raise AravisException(f"Feature {name} does not seem to exist in camera")
        return node.get_node_name()

    def get_feature(self, name):
        """
        return value of a feature. independently of its type
        """
        ntype = self.get_feature_type(name)
        if ntype in ("Enumeration", "String", "StringReg"):
            return self.dev.get_string_feature_value(name)
        elif ntype == "Integer":
            return self.dev.get_integer_feature_value(name)
        elif ntype == "Float":
            return self.dev.get_float_feature_value(name)
        elif ntype == "Boolean":
            return self.dev.get_integer_feature_value(name)
        else:
            self.logger.warning("Feature type not implemented: %s", ntype)

    def set_feature(self, name, val):
        """
        set value of a feature
        """
        ntype = self.get_feature_type(name)
        if ntype in ("String", "Enumeration", "StringReg"):
            return self.dev.set_string_feature_value(name, val)
        elif ntype == "Integer":
            return self.dev.set_integer_feature_value(name, int(val))
        elif ntype == "Float":
            return self.dev.set_float_feature_value(name, float(val))
        elif ntype == "Boolean":
            return self.dev.set_boolean_feature_value(name, int(val))
        else:
            self.logger.warning("Feature type not implemented: %s", ntype)

    def get_genicam(self):
        """
        return genicam xml from the camera
        """
        return self.dev.get_genicam_xml()

    def get_feature_vals(self, name):
        """
        if feature is an enumeration then return possible values
        """
        ntype = self.get_feature_type(name)
        if ntype == "Enumeration":
            return self.dev.get_available_enumeration_feature_values_as_strings(name)
        else:
            raise AravisException(f"{name} is not an enumeration but a {ntype}")

    def read_register(self, address):
        return self.dev.read_register(address)

    def write_register(self, address, val):
        return self.dev.write_register(address, val)

    def create_buffers(self, nb=10, payload=None):
        if not payload:
            payload = self.cam.get_payload()
        self.logger.info("Creating %s memory buffers of size %s", nb, payload)
        for _ in range(0, nb):
            self.stream.push_buffer(Aravis.Buffer.new_allocate(payload))

    def pop_frame(self, timestamp=False):
        while True: #loop in python in order to allow interrupt, have the loop in C might hang
            if timestamp:
                ts, frame = self.try_pop_frame(timestamp)
            else:
                frame = self.try_pop_frame()

            if frame is None:
                time.sleep(0.001)
            else:
                if timestamp:
                    return ts, frame
                else:
                    return frame

    def try_pop_frame(self, timestamp=False):
        """
        return the oldest frame in the aravis buffer
        """
        buf = self.stream.try_pop_buffer()
        if buf and buf.get_payload_type() == Aravis.BufferPayloadType.IMAGE:
            frame = self._array_from_buffer_address(buf)
            self.stream.push_buffer(buf)
            if timestamp:
                return buf.get_timestamp(), frame
            else:
                return frame
        else:
            if timestamp:
                return None, None
            else:
                return None

    def _array_from_buffer_address(self, buf):
        if not buf:
            return None
        pixel_format = buf.get_image_pixel_format()
        bits_per_pixel = pixel_format >> 16 & 0xff
        if bits_per_pixel == 8:
            INTP = ctypes.POINTER(ctypes.c_uint8)
        else:
            INTP = ctypes.POINTER(ctypes.c_uint16)
        addr = buf.get_data()
        ptr = ctypes.cast(addr, INTP)
        im = np.ctypeslib.as_array(ptr, (buf.get_image_height(), buf.get_image_width()))
        im = im.copy()
        return im

    def trigger(self):
        """
        trigger camera to take a picture when camera is in software trigger mode
        """
        self.execute_command("TriggerSoftware")

    def __str__(self):
        return "Camera: " + self.name

    def __repr__(self):
        return self.__str__()
    
    def start_acquisition(self, nb_buffers=10):
        self.logger.info("starting acquisition")
        payload = self.cam.get_payload()
        if payload != self._last_payload:
            #FIXME should clear buffers
            self.create_buffers(nb_buffers, payload) 
            self._last_payload = payload
        self.cam.start_acquisition()

    def start_acquisition_trigger(self, nb_buffers=1):
        self.set_feature("AcquisitionMode", "Continuous") #no acquisition limits
        self.set_feature("TriggerSource", "Software") #wait for trigger t acquire image
        self.set_feature("TriggerMode", "On") #Not documented but necessary
        self.start_acquisition(nb_buffers)

    def start_acquisition_continuous(self, nb_buffers=20):
        self.set_feature("AcquisitionMode", "Continuous") #no acquisition limits
        # self.set_feature("TriggerSource", "Freerun") #as fast as possible
        # self.set_string_feature("TriggerSource", "FixedRate") 
        # self.set_feature("TriggerMode", "On") #Not documented but necessary
        self.start_acquisition(nb_buffers)

    def stop_acquisition(self):
        self.cam.stop_acquisition()

    def shutdown(self):
        # Delete the objects on shutdown: socket will be closed!
        del self.stream
        del self.dev
        del self.cam

def get_device_ids():
    Aravis.update_device_list()
    n = Aravis.get_n_devices()
    return [Aravis.get_device_id(i) for i in range(0, n)]

def save_genicam_xml(self, file_path):
    """
    Save the Genicam XML data to a file.
    """
    xml_data, size = self.get_genicam_xml()
    if xml_data is None or size == 0:
        raise AravisException("Failed to retrieve Genicam XML data")

    with open(file_path, 'wb') as file:
        file.write(xml_data.encode("utf-8")[:size])

    print(f"Genicam XML content has been written to {file_path}")



def config_basler(cam : Camera):
    cam.set_feature("Width", 1920)
    cam.set_feature("Height", 1080)
    cam.set_feature("AcquisitionFrameRate", cam.cam.get_frame_rate_bounds()[1])
    cam.set_feature("AcquisitionFrameRateEnable", 1)
    cam.set_feature("PixelFormat", "BayerRG8")
    


def config_tiscam(cam : Camera):
    cam.set_feature("Width", 1920)
    cam.set_feature("Height", 1080)
    cam.set_feature("AcquisitionFrameRate", cam.cam.get_frame_rate_bounds()[1])
    cam.set_feature("PixelFormat", "BayerRG8")
    


def print_device_info(cam : Camera):
    print("\n==========================")
    print(f"Vendor:         {cam.cam.get_vendor_name()}")
    print(f"Model:          {cam.cam.get_model_name()}")
    print(f"Serial:         {cam.cam.get_device_serial_number()}")

    print(f"    AVAILABLE:  ")
    print(f"Width:          {cam.cam.get_width_bounds()}")
    print(f"Height:         {cam.cam.get_height_bounds()}")
    print(f"Frame rate:     {cam.cam.get_frame_rate_bounds()}")
    print(f"Pixel format:   {cam.cam.dup_available_pixel_formats_as_strings()}")
    print(f"Exposure:       {cam.cam.get_exposure_time_bounds()}")
    print(f"ExposureLow:    {cam.get_feature('AutoExposureTimeLowerLimit')}")
    print(f"ExposureHigh:   {cam.get_feature('AutoExposureTimeUpperLimit')}")
    print(f"Gain:           {cam.cam.get_gain_bounds()}")


    print(f"    CURRENT:  ")
    print(f"Width:          {cam.cam.get_region()[2]}")
    print(f"Height:         {cam.cam.get_region()[3]}")
    print(f"Frame rate:     {cam.cam.get_frame_rate()}")
    print(f"Pixel format:   {cam.cam.get_pixel_format_as_string()}")
    print(f"Exposure time:  {cam.cam.get_exposure_time()}")
    print(f"Exposure auto:  {Aravis.Auto.to_string(cam.cam.get_exposure_time_auto())}")
    print(f"Gain:           {cam.cam.get_gain()}")
    print(f"Gain auto:      {Aravis.Auto.to_string(cam.cam.get_gain_auto())}")
    print("==========================\n")

def camera_process(ip, cam_type, frame_dict, lock):
    try:
        cam = Camera(ip)
        if cam_type == 'tis':
            config_tiscam(cam)
        elif cam_type == 'basler':
            config_basler(cam)
        
        cam.start_acquisition_continuous(nb_buffers=50)

        while True:
            ts, frame = cam.try_pop_frame(timestamp=True)
            if frame is not None:
                frame = cv2.cvtColor(frame, cv2.COLOR_BAYER_RG2RGB)
                with lock:
                    frame_dict[ip] = frame
            time.sleep(0.01)
    except AravisException as e:
        print(f"Failed to initialize camera with IP {ip}: {e}")
    finally:
        cam.stop_acquisition()
        cam.shutdown()

def display_process(frame_dict, lock):
    while True:
        with lock:
            frames = list(frame_dict.values())
        
        if len(frames) > 0:
            combined_frame = np.hstack(frames)
            cv2.imshow("Combined Camera Feed", combined_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()

def multiple():
    manager = mp.Manager()
    frame_dict = manager.dict()
    lock = mp.Lock()

    processes = []
    for ip, cam_type in ips.items():
        p = mp.Process(target=camera_process, args=(ip, cam_type, frame_dict, lock))
        p.start()
        processes.append(p)

    display_p = mp.Process(target=display_process, args=(frame_dict, lock))
    display_p.start()
    processes.append(display_p)

    for p in processes:
        p.join()


def main():
    # Create the camera object

    for i in range(1):
        
        ip = "10.1.3.76"

        cam = Camera(ip)

        if ips[ip] == 'tis':
            config_tiscam(cam)
        elif ips[ip] == 'basler':
            config_basler(cam)  


        try:
            # Start continuous acquisition
            cam.start_acquisition_continuous(nb_buffers=50)

            # OpenCV window
            cv2.namedWindow("Aravis Camera", cv2.WINDOW_AUTOSIZE)

            fps = 0
            last_ts = 0
            last_fps_display = time.time()

            while True:
                # Pop a frame from the camera
                start = time.time_ns()
                ts, frame = cam.try_pop_frame(timestamp=True)
                end = time.time_ns()
                # print(f"Pop:        {end - start} ns     ({(end - start) / 1000000} ms)")
                
                # Convert the frame to a format suitable for OpenCV
                start = time.time_ns()
                if frame is not None:
                    if frame.ndim == 2:  # Grayscale image
                        # cv2.imshow("Aravis Camera", frame)
                        cv2.imshow("Aravis Camera", cv2.cvtColor(frame, cv2.COLOR_BAYER_RG2RGB))
                    else:  # Color image
                        cv2.imshow("Aravis Camera", cv2.cvtColor(frame, cv2.COLOR_BAYER_RG2RGB))
                end = time.time_ns()
                # print(f"Convert:    {end - start} ns     ({(end - start) / 1000000} ms)")

                # Calculate FPS
                if ts is not None:
                    delta = ts - last_ts
                    if delta > 0.0:
                        fps = 1000000000.0 / (ts - last_ts)
                    last_ts = ts

                # Display FPS
                if time.time() - last_fps_display > 1.0:
                    last_fps_display = time.time()
                    print(f"FPS: {fps:.2f}")

                # Exit loop on 'q' key press
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                


        finally:
            # Stop acquisition and release resources
            cam.stop_acquisition()
            cam.shutdown()
            cv2.destroyAllWindows()

        time.sleep(1)


if __name__ == "__main__":
    main()
    # multiple()