import gi
import sys
import argparse
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GObject, GLib, GstRtspServer

# Initialize GStreamer
Gst.init(None)

def create_source_bin(uri):
    print("Creating source bin")

    nbin = Gst.Bin.new("source-bin")
    if not nbin:
        sys.stderr.write("Unable to create source bin\n")

    uri_decode_bin = Gst.ElementFactory.make("decodebin", "uri-decode-bin")
    if not uri_decode_bin:
        sys.stderr.write("Unable to create uri decode bin\n")

    # deeuri_decode_bin.set_property("uri", uri)

    def decodebin_child_added(child_proxy, Object, name, user_data):
        print(f"Child added: {name}")
        if "decodebin" in name:
            Object.connect("child-added", decodebin_child_added, user_data)

    uri_decode_bin.connect("child-added", decodebin_child_added, nbin)

    Gst.Bin.add(nbin, uri_decode_bin)
    ghost_pad = Gst.GhostPad.new_no_target("src", Gst.PadDirection.SRC)
    nbin.add_pad(ghost_pad)

    uri_decode_bin.connect("pad-added", cb_newpad, ghost_pad)

    return nbin

def cb_newpad(decodebin, decoder_src_pad, ghost_pad):
    print("New pad added to decodebin:", decoder_src_pad.get_name())
    if not ghost_pad.set_target(decoder_src_pad):
        print("Failed to link decoder src pad to source bin ghost pad")

class RTSPServer(GstRtspServer.RTSPMediaFactory):
    def __init__(self, pipeline):
        super(RTSPServer, self).__init__()
        self.pipeline = pipeline

    def do_create_element(self, url):
        return self.pipeline

def main(args):
    pipeline = Gst.Pipeline.new("pipeline")

    source_bin = create_source_bin(args.uri)
    pipeline.add(source_bin)

    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "nvvidconv")
    if not nvvidconv:
        sys.stderr.write("Unable to create nvvideoconvert\n")
        return

    encoder = Gst.ElementFactory.make("nvv4l2h264enc", "encoder")
    if not encoder:
        sys.stderr.write("Unable to create nvv4l2h264enc\n")
        return

    rtppay = Gst.ElementFactory.make("rtph264pay", "rtppay")
    if not rtppay:
        sys.stderr.write("Unable to create rtph264pay\n")
        return

    pipeline.add(nvvidconv)
    pipeline.add(encoder)
    pipeline.add(rtppay)

    def on_pad_added(element, pad, target):
        print(f"New pad added: {pad.get_name()}")
        sink_pad = target.get_static_pad("sink")
        if not sink_pad.is_linked():
            if pad.link(sink_pad) != Gst.PadLinkReturn.OK:
                print(f"Failed to link pad {pad.get_name()} to {target.get_name()}")

    source_bin.get_by_name("uri-decode-bin").connect("pad-added", on_pad_added, nvvidconv)

    if not nvvidconv.link(encoder):
        sys.stderr.write("Unable to create rtph264pay\n")
        return

    if not encoder.link(rtppay):
        sys.stderr.write()


    # Create RTSP server
    server = GstRtspServer.RTSPServer.new()
    server.set_service("8554")
    mounts = server.get_mount_points()

    factory = RTSPServer(pipeline)
    factory.set_shared(False)
    factory.set_latency(0)
    mounts.add_factory("/test", factory)

    server.attach(None)

    loop = GLib.MainLoop()

    def bus_call(bus, message, loop):
        if message.type == Gst.MessageType.EOS:
            print("End of stream")
            loop.quit()
        elif message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}, {debug}")
            loop.quit()
        return True

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    print("Preparing pipeline")
    pipeline.set_state(Gst.State.PAUSED)

    print("Starting pipeline")
    pipeline.set_state(Gst.State.PLAYING)

    print("RTSP stream ready at rtsp://127.0.0.1:8554/test")

    try:
        loop.run()
    except Exception as e:
        print(f"Error in main loop: {e}")

    print("Stopping pipeline")
    pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RTSP Input to RTSP Output')
    parser.add_argument('uri', type=str, help='URI of the RTSP input stream')
    args = parser.parse_args()

    main(args)
