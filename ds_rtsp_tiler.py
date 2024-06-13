#!/usr/bin/env python3

import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GLib, GstRtspServer
from gi.repository import GObject

Gst.init(None)

# Check input arguments
if len(sys.argv) < 2:
    sys.stderr.write("Usage: %s <RTSP URI> [RTSP URI ...]\n" % sys.argv[0])
    sys.exit(1)

# List of RTSP URIs
rtsp_uris = sys.argv[1:]

def bus_call(bus, message, loop):
    t = message.type
    if t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print(f"Error: {err}, {debug}")
        loop.quit()
    elif t == Gst.MessageType.EOS:
        print("End-Of-Stream reached")
        loop.quit()
    elif t == Gst.MessageType.WARNING:
        err, debug = message.parse_warning()
        print(f"Warning: {err}, {debug}")
    return True

def create_rtsp_source(uri):
    source = Gst.ElementFactory.make("rtspsrc", None)
    source.set_property("location", uri)
    source.set_property("latency", 200)
    return source

def main():
    # Create GStreamer pipeline
    pipeline = Gst.Pipeline()

    # Create stream muxer
    streammux = Gst.ElementFactory.make("nvstreammux", "stream-muxer")
    streammux.set_property("width", 1920)
    streammux.set_property("height", 1080)
    streammux.set_property("batch-size", len(rtsp_uris))
    streammux.set_property("batched-push-timeout", 4000000)
    pipeline.add(streammux)

    # Add RTSP sources
    for i, uri in enumerate(rtsp_uris):
        source_bin = create_rtsp_source(uri)
        pipeline.add(source_bin)
        source_bin.connect("pad-added", on_rtsp_pad_added, streammux, i)
    
    # Create other elements
    # nvinfer = Gst.ElementFactory.make("nvinfer", "primary-inference")
    # nvinfer.set_property("config-file-path", "config_infer_primary.txt")
    # pipeline.add(nvinfer)

    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "nvvideo-converter")
    pipeline.add(nvvidconv)

    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
    pipeline.add(nvosd)

    nvtiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
    nvtiler.set_property("rows", 2)
    nvtiler.set_property("columns", 2)
    nvtiler.set_property("width", 1920)
    nvtiler.set_property("height", 1080)
    pipeline.add(nvtiler)

    sink = Gst.ElementFactory.make("nveglglessink", "nvvideo-renderer")
    pipeline.add(sink)

    # Link elements
    streammux.link(nvtiler)
    #nvinfer.link(nvtiler)
    nvtiler.link(nvvidconv)
    nvvidconv.link(nvosd)
    nvosd.link(sink)

    # Create a GLib Main Loop and set bus to call bus_call
    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    # Start play back and listen to events
    print("Starting pipeline")
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass

    # Cleanup
    print("Stopping pipeline")
    pipeline.set_state(Gst.State.NULL)

def on_rtsp_pad_added(src, pad, muxer, index):
    sinkpad = muxer.request_pad(f"sink_{index}")
    pad.link(sinkpad)

if __name__ == '__main__':
    sys.exit(main())
