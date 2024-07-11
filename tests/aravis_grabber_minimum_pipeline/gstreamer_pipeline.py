import numpy as np
from multiprocessing import shared_memory
import gi

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib


class GStreamerPipeline:
    def __init__(self, frame_width, frame_height, shm_name):
        self.frame_shape = (frame_height, frame_width)
        self.shm_name = shm_name

        self.frame_size = np.prod(self.frame_shape)
        self.shm = shared_memory.SharedMemory(name=self.shm_name)
        self.frame_buffer = np.ndarray(self.frame_shape, dtype=np.uint8, buffer=self.shm.buf)
        

        Gst.init(None)
        self.pipeline = Gst.Pipeline()

        self.appsrc = Gst.ElementFactory.make("appsrc", "source")
        self.queue = Gst.ElementFactory.make("queue", "queue")
        self.debayer = Gst.ElementFactory.make("bayer2rgb", "debayer")
        self.convert = Gst.ElementFactory.make("videoconvert", "convert")
        self.sink = Gst.ElementFactory.make("xvimagesink", "sink")

        self.appsrc.set_property("caps", Gst.Caps.from_string(f"video/x-bayer, \
            format=rggb, \
            width={self.frame_shape[1]}, \
            height={self.frame_shape[0]}, \
            framerate=(fraction)54/1"))
        self.appsrc.set_property("max-buffers", 1)
        self.appsrc.set_property("max-bytes", 0)
        self.appsrc.set_property("max-time", 0)
        self.appsrc.set_property("leaky-type", 1)

        self.queue.set_property("leaky", 1)  # Dropping old buffers
        self.queue.set_property("max-size-buffers", 1)
        self.queue.set_property("max-size-bytes", 0)
        self.queue.set_property("max-size-time", 0)

        self.convert.set_property("n-threads", 4)

        self.sink.set_property("sync", False)




        self.pipeline.add(self.appsrc)
        self.pipeline.add(self.queue)
        self.pipeline.add(self.debayer)
        self.pipeline.add(self.convert)
        self.pipeline.add(self.sink)

        self.appsrc.link(self.queue)
        self.queue.link(self.debayer)
        self.debayer.link(self.convert)
        self.convert.link(self.sink)

        

    def start_pipeline(self):
        print("=== Start Pipeline ===\n")
        self.pipeline.set_state(Gst.State.PLAYING)
        GLib.timeout_add(1, self.push_frame)

        loop = GLib.MainLoop()
        try:
            loop.run()
        except KeyboardInterrupt:
            print("=== Stop Pipeline ===\n")
            self.pipeline.set_state(Gst.State.NULL)

        

    def push_frame(self):
        gst_buffer = Gst.Buffer.new_wrapped(self.frame_buffer.tobytes())
        self.appsrc.emit("push-buffer", gst_buffer)
        return True
