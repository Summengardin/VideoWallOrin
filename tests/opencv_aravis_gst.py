import cv2
import gi
import numpy as np
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib, GObject

Gst.init(None)

def create_source_bin(camera_name, bin_name):
    bin = Gst.Bin.new(bin_name)
    if not bin:
        print(f"Failed to create the bin for {camera_name}.")
        return None
    source = Gst.ElementFactory.make("aravissrc", "source")
    if not source:
        print(f"Failed to create the source element for {camera_name}.")
        return None

    source.set_property("camera-name", camera_name)
    # source.set_property("num-arv-buffers", 64)
    # source.set_property("packet-resend", False)
    # source.set_property("packet-size", 9000)
    # source.set_property("auto-packet-size", False)

    convert = Gst.ElementFactory.make("videoconvert", "convert")
    if not convert:
        print(f"Failed to create the convert element for {camera_name}.")
    sink = Gst.ElementFactory.make("appsink", "sink")
    if not sink:
        print(f"Failed to create the sink element for {camera_name}.")

    sink.set_property("emit-signals", True)
    sink.set_property("sync", False)
    sink.set_property("max-buffers", 1)
    sink.set_property("drop", True)
    
    bin.add(source)
    bin.add(convert)
    bin.add(sink)
    
    if not source.link(convert):
        print("Failed to link source to convert")
    if not convert.link(sink):
        print("Failed to link convert to sink")

    return bin, sink

def on_new_sample(sink, data):
    sample = sink.emit("pull-sample")
    buf = sample.get_buffer()
    caps = sample.get_caps()
    try:
        print(f"Buffer size: {buf.get_size()}   height: {caps.get_structure(0).get_value('height')}   width: {caps.get_structure(0).get_value('width')}" )
        arr = np.ndarray(
            (
                caps.get_structure(0).get_value("height"),
                caps.get_structure(0).get_value("width"),
                3,
            ),
            # buffer=buf.extract_dup(0, buf.get_size()),
            buffer=buf.extract_dup(0,  buf.get_size()),
            dtype=np.uint8,
        )
        data.append(arr)
    except Exception as e:
        print(f"Error processing buffer: {e}")
    return Gst.FlowReturn.OK

def main():
    pipeline = Gst.Pipeline.new("camera_pipeline")
    
    cam1 = "10.1.3.75"
    cam2 = "10.1.3.76"
    
    bin1, appsink1 = create_source_bin(cam1, "source_bin1")
    bin2, appsink2 = create_source_bin(cam2, "source_bin2")
    
    if not bin1 or not bin2:
        print("Failed to create source bins.")
        return

    pipeline.add(bin1)
    pipeline.add(bin2)

    pipeline.set_state(Gst.State.PLAYING)
    

    feed1 = []
    feed2 = []

    appsink1.connect("new-sample", on_new_sample, feed1)
    appsink2.connect("new-sample", on_new_sample, feed2)

    def display_feeds():
        while True:
            if feed1 and feed2:
                frame1 = feed1.pop(0)
                frame2 = feed2.pop(0)
                combined_frame = np.hstack((frame1, frame2))
                cv2.imshow("Camera Feeds", combined_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    display_feeds()

    pipeline.set_state(Gst.State.NULL)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
