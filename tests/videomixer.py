import argparse
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

def launch_cameras(cams, dbg):
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

    # Initialize GStreamer
    Gst.init(None)

    # Create GStreamer pipeline
    pipeline = Gst.Pipeline.new("camera-pipeline")

    streammux = Gst.ElementFactory.make("nvstreammux", "mux")
    nvtiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
    sink = Gst.ElementFactory.make("nv3dsink", "sink")
    sink.set_property("sync", False)

    if not pipeline or not streammux or not nvtiler or not sink:
        print("Not all elements could be created.")
        return

    pipeline.add(streammux)
    pipeline.add(nvtiler)
    pipeline.add(sink)

    if not streammux.link(nvtiler) or not nvtiler.link(sink):
        print("Elements could not be linked.")
        return

    streammux.set_property("batch-size", 4)



    for i, cam in enumerate(cams):
        if cam in camera_properties:
            props = camera_properties[cam]
            width = props["width"]
            height = props["height"]
            framerate = props["framerate"]
            fmt = props["format"]

            # Create elements for each camera
            source = Gst.ElementFactory.make("aravissrc", f"source_{i}")
            cam_caps = Gst.ElementFactory.make("capsfilter", f"caps_{i}")
            tcamconvert = Gst.ElementFactory.make("tcamconvert", f"tcamconvert_{i}")
            videoconvert = Gst.ElementFactory.make("videoconvert", f"videoconvert_{i}")
            nvconvert = Gst.ElementFactory.make("nvvideoconvert", f"nvconvert_{i}")
            conv_caps = Gst.ElementFactory.make("capsfilter", f"conv_caps_{i}")
            queue = Gst.ElementFactory.make("queue", f"queue_{i}")

            if not (source and cam_caps and tcamconvert and videoconvert and queue and nvconvert):
                print(f"Not all elements could be created for camera {cam}.")
                continue

            source.set_property("camera-name", cam)
            cam_caps.set_property("caps", Gst.Caps.from_string(f"video/x-bayer,width={width},height={height},framerate={framerate},format={fmt}"))
            conv_caps.set_property("caps", Gst.Caps.from_string(f"video/x-raw(memory:NVMM),format=NV12"))

            pipeline.add(source)
            pipeline.add(cam_caps)
            pipeline.add(tcamconvert)
            pipeline.add(videoconvert)
            pipeline.add(nvconvert)
            pipeline.add(conv_caps)
            pipeline.add(queue)

            q_pad = queue.get_static_pad("src")
            m_pad = streammux.request_pad_simple(f"sink_{i}")
            x_pos = i % 2 * 1920
            y_pos = i // 2 * 1080
            

            if not (q_pad and m_pad):
                print("Pads could not be retrieved.")
                continue
            
            q_pad.link(m_pad)

            if not (source.link(cam_caps) and cam_caps.link(tcamconvert) and tcamconvert.link(videoconvert) and videoconvert.link(nvconvert) and nvconvert.link(conv_caps) and conv_caps.link(queue)):
                print(f"Elements could not be linked for camera {cam}.")
                continue

    # Start playing
    pipeline.set_state(Gst.State.PLAYING)

    loop = GLib.MainLoop()
    print("Running the main loop...")
    try:
        loop.run()
    except KeyboardInterrupt:
        pass

    # Free resources
    pipeline.set_state(Gst.State.NULL)

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

    launch_cameras(cams, dbg)

if __name__ == "__main__":
    main()
