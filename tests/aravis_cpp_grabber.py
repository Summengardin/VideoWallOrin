# Reference: gst-launch-1.0 aravissrc camera-name=10.1.3.76 ! 'video/x-bayer,format=(string)rggb,width=1920,height=1080,framerate=(fraction)60/1' ! bayer2rgb ! videoconvert ! xvimagesink sync=false

import ctypes
import numpy as np

# Load the shared library
lib = ctypes.cdll.LoadLibrary('./cpp/build/libframe_grabber.so')

# Define the functions
lib.start_frame_grabber.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ]
lib.start_frame_grabber.restype = None

lib.stop_frame_grabber.argtypes = []
lib.stop_frame_grabber.restype = None

lib.get_frame.argtypes = [ctypes.POINTER(ctypes.c_uint8)]
lib.get_frame.restype = None

# Start the frame grabber
camera_name = "10.1.3.76".encode('utf-8')
width, height = 1920, 1080
framerate = 60
lib.start_frame_grabber(width, height, framerate, camera_name)

# Create a numpy array to hold the frame data
frame_data = np.zeros((height, width), dtype=np.uint8)

# Define a function to get a frame
def get_frame():
    lib.get_frame(frame_data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)))
    return frame_data

# Example usage with GStreamer pipeline
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

class GStreamerPipeline:
    def __init__(self, width, height, framerate):
        Gst.init(None)
        self.pipeline = Gst.Pipeline()

        self.appsrc = Gst.ElementFactory.make("appsrc", "source")
        self.bayer2rgb = Gst.ElementFactory.make("bayer2rgb", "bayer2rgb")
        self.convert = Gst.ElementFactory.make("videoconvert", "convert")
        self.sink = Gst.ElementFactory.make("xvimagesink", "sink")

        self.pipeline.add(self.appsrc)
        self.pipeline.add(self.bayer2rgb)
        self.pipeline.add(self.convert)
        self.pipeline.add(self.sink)

        self.appsrc.link(self.bayer2rgb)
        self.bayer2rgb.link(self.convert)
        self.convert.link(self.sink)

        self.appsrc.set_property("caps", Gst.Caps.from_string(
            "video/x-bayer,format=(string)rggb,width={},height={},framerate=(fraction){}/1".format(width, height, framerate)))
        self.appsrc.set_property("max-buffers", 1)
        self.appsrc.set_property("max-bytes", 0)
        self.appsrc.set_property("max-time", 0)
        self.appsrc.set_property("leaky-type", 1)
        self.appsrc.connect("need-data", self.push_frame)

        self.buffer_cnt = 0

    def start_pipeline(self):
        print("=== Start Pipeline ===\n")
        self.pipeline.set_state(Gst.State.PLAYING)
        
        GLib.timeout_add(1000, self.print_fps)
        # GLib.timeout_add(10, self.push_frame)
        # self.appsrc

        loop = GLib.MainLoop()
        try:
            loop.run()
        except KeyboardInterrupt:
            print("=== Stop Pipeline ===\n")
            self.pipeline.set_state(Gst.State.NULL)

    def push_frame(self, length, user_data):
        frame = get_frame()
        gst_buffer = Gst.Buffer.new_wrapped(frame.tobytes())
        self.appsrc.emit("push-buffer", gst_buffer)
        self.buffer_cnt += 1
        return True
    
    def print_fps(self):
        print(self.buffer_cnt)
        self.buffer_cnt = 0
        return True

pipeline = GStreamerPipeline(width, height, framerate)
try:
    pipeline.start_pipeline()
except Exception as e:
    print(e)

lib.stop_frame_grabber()