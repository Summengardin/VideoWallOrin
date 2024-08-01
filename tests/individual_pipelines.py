import argparse
import multiprocessing as mp
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

def launch_camera(cam, dbg):
    # Properties for each camera
    camera_properties = {
        "10.1.3.75": {
            "width": 1920,
            "height": 1080,
            "framerate": "54/1",
            "format": "rggb"
        },
        "10.1.3.74": {
            "width": 1920,
            "height": 1080,
            "framerate": "100/1",
            "format": "rggb"
        },
        "10.1.3.76": {
            "width": 1920,
            "height": 1080,
            "framerate": "100/1",
            "format": "rggb"
        },
        "10.1.3.77": {
            "width": 1920,
            "height": 1080,
            "framerate": "100/1",
            "format": "rggb"
        }
    }

    # Determine camera properties
    if cam in camera_properties:
        props = camera_properties[cam]
        width = props["width"]
        height = props["height"]
        framerate = props["framerate"]
        fmt = props["format"]

        # Initialize GStreamer
        Gst.init(None)

        # Create GStreamer pipeline elements
        pipeline = Gst.Pipeline.new("camera-pipeline")

        source = Gst.ElementFactory.make("aravissrc", "source")
        source.set_property("camera-name", cam)

        caps = Gst.ElementFactory.make("capsfilter", "caps")
        caps.set_property("caps", Gst.Caps.from_string(f"video/x-bayer,width={width},height={height},framerate={framerate},format={fmt}"))

        tcamconvert = Gst.ElementFactory.make("tcamconvert", "tcamconvert")
        videoconvert = Gst.ElementFactory.make("videoconvert", "videoconvert")
        sink = Gst.ElementFactory.make("xvimagesink", "sink")
        sink.set_property("sync", False)

        if not (pipeline and source and caps and tcamconvert and videoconvert and sink):
            print("Not all elements could be created.")
            return

        # Build the pipeline
        pipeline.add(source)
        pipeline.add(caps)
        pipeline.add(tcamconvert)
        pipeline.add(videoconvert)
        pipeline.add(sink)

        if not (source.link(caps) and caps.link(tcamconvert) and tcamconvert.link(videoconvert) and videoconvert.link(sink)):
            print("Elements could not be linked.")
            return

        # Start playing
        pipeline.set_state(Gst.State.PLAYING)

        # Wait until error or EOS
        bus = pipeline.get_bus()
        msg = bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE, Gst.MessageType.ERROR | Gst.MessageType.EOS)

        # Parse message
        if msg:
            if msg.type == Gst.MessageType.ERROR:
                err, debug = msg.parse_error()
                print(f"Error: {err}, {debug}")
            elif msg.type == Gst.MessageType.EOS:
                print("End-Of-Stream reached")

        # Free resources
        pipeline.set_state(Gst.State.NULL)
    else:
        print(f"Camera IP {cam} not recognized.")

def main():
    # Default values
    cam_default = ["10.1.3.75", "10.1.3.74", "10.1.3.76", "10.1.3.77"]
    dbg_default = "0"

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Display camera feed.')
    parser.add_argument('cams', nargs='*', default=cam_default, help='Camera IP addresses')
    parser.add_argument('dbg', nargs='?', default=dbg_default, help='Debug level')
    args = parser.parse_args()

    cams = args.cams
    dbg = args.dbg

    processes = []

    for cam in cams:
        process = mp.Process(target=launch_camera, args=(cam, dbg))
        process.start()
        processes.append(process)

    for process in processes:
        process.join()

if __name__ == "__main__":
    main()
