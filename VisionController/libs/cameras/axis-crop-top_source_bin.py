import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

import logging
logger = logging.getLogger(__name__)

if not Gst.is_initialized():
    Gst.init(None)


def create_source_bin(index: int, camera=None) -> Gst.Bin:
    if camera is None or getattr(camera, "uri", None) is None:
        uri = "file:///app/VisionController/data/assets/image_placeholder.png"
    else:
        uri = camera.uri

    logger.debug(f"Creating nvurisrcbin for {uri}")

    bin_name = f"src{index}-bin"
    bin = Gst.Bin.new(bin_name)
    if not bin:
        logger.error("Unable to create bin")
        return None

    nvurisrcbin = Gst.ElementFactory.make("nvurisrcbin", f"src{index}-nvurisrcbin")
    if not nvurisrcbin:
        logger.error("Unable to create nvurisrcbin")
        return None

    nvurisrcbin.set_property("uri", uri)
    nvurisrcbin.set_property("latency", 0)
    nvurisrcbin.set_property("low-latency-mode", 1)
    nvurisrcbin.set_property("drop-frame-interval", 0)
    nvurisrcbin.set_property("num-extra-surfaces", 6)
    nvurisrcbin.set_property("file-loop", 1)
    nvurisrcbin.set_property("rtsp-reconnect-interval", 0)
    nvurisrcbin.set_property("rtsp-reconnect-attempts", 0)
    # Optional on multi-GPU x86: nvurisrcbin.set_property("gpu-id", 0)

    nvurisrcbin.connect("pad-added", nvurisrcbin_pad_added, (bin, index))
    nvurisrcbin.connect("child-added", decodebin_child_added, bin)

    # GPU convert does: crop (pre-rotate), then rotate to 1920x1080
    nvconvert = Gst.ElementFactory.make("nvvideoconvert", f"src{index}-nvvideoconvert")
    nvconvert.set_property("compute-hw", "GPU")
    # Crop 1080x1920 region (portrait) from the left/top of the rotated frame.
    # This corresponds to the "top" of the original vertical image.
    nvconvert.set_property("src-crop", "0:0:1080:1920")
    # Rotate 90° clockwise to correct the source that is 90° CCW
    nvconvert.set_property("flip-method", 3)
    # Optional on multi-GPU x86: nvconvert.set_property("gpu-id", 0)

    # Constrain final caps AFTER convert. Now it's true 1920x1080 in NVMM/NV12.
    capsfilter = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter")
    if not capsfilter:
        logger.error(f"Unable to create capsfilter for source {index}")
        return None
    caps_string = "video/x-raw(memory:NVMM), format=NV12, width=1920, height=1080"
    caps = Gst.Caps.from_string(caps_string)
    capsfilter.set_property("caps", caps)
    logger.debug(f"Set capsfilter of bin source {index} to '{caps_string}'")

    queue = Gst.ElementFactory.make("queue", f"src{index}-queue")
    if not queue:
        logger.error(f"Unable to create queue for source {index}")
        return None
    queue.set_property("leaky", 2)
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)
    queue.set_property("silent", 1)

    bin.add(nvurisrcbin)
    bin.add(nvconvert)
    bin.add(capsfilter)
    bin.add(queue)

    # Delayed link: nvurisrcbin -> (pad-added) -> nvvideoconvert
    if not nvconvert.link(capsfilter):
        logger.error(f"Unable to link nvvideoconvert to capsfilter for source {index}")
        return None

    if not capsfilter.link(queue):
        logger.error(f"Unable to link capsfilter to queue for source {index}")
        return None

    # PRE-CREATE ghost pad with no target
    src_pad = queue.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))
    return bin


def decodebin_child_added(child_proxy, Object, name, data):
    element_type = Object.get_factory().get_name()
    logger.debug(f"Child added: {name} ({element_type})")
    if element_type == "decodebin":
        Object.connect("child-added", decodebin_child_added, data)

    if element_type == "nvv4l2decoder":
        Object.set_property("low-latency-mode", 1)
        Object.set_property("drop-frame-interval", 0)

    elif element_type == "queue":
        if name != "dec_queue":
            Object.set_property("max-size-buffers", 1)
            Object.set_property("max-size-bytes", 0)
            Object.set_property("max-size-time", 0)
            Object.set_property("leaky", 2)
            Object.set_property("silent", 1)
        else:
            Object.set_property("max-size-buffers", 5)
            Object.set_property("max-size-bytes", 0)
            Object.set_property("max-size-time", 0)
            Object.set_property("leaky", 2)
            Object.set_property("silent", 1)


def nvurisrcbin_pad_added(srcbin, pad, data):
    source_bin, index = data
    logger.debug(f"Linking video pad {pad.get_name()} to nvvideoconvert sink")
    nvconvert = source_bin.get_by_name(f"src{index}-nvvideoconvert")
    sink_pad = nvconvert.get_static_pad("sink")
    if not sink_pad:
        logger.error("Unable to get nvvideoconvert sink pad")
        return
    if pad.link(sink_pad) != Gst.PadLinkReturn.OK:
        logger.error("Failed to link nvurisrcbin pad to nvvideoconvert sink")
        return
    logger.debug(f"Pad {pad.get_name()} linked to nvvideoconvert sink pad.")


if __name__ == "__main__":
    from gi.repository import Gst, GLib

    Gst.init(None)

    camera = type('Camera', (object,), {'uri': 'rtsp://root:root@10.1.3.80/axis-media/media.amp?streamprofile=stream-1'})

    bin = create_source_bin(0, camera)
    if bin:
        print("Source bin created successfully.")
    else:
        print("Failed to create source bin.")
    Gst.debug_bin_to_dot_file(bin, Gst.DebugGraphDetails.ALL, "test_source_bin")
    print("Debug graph written to 'test_source_bin.dot'.")

    pipeline = Gst.Pipeline.new("test-pipeline")
    if not pipeline:
        print("Failed to create pipeline")
    else:
        pipeline.add(bin)

        conv = Gst.ElementFactory.make("nvvideoconvert", "conv")  # optional extra convert
        sink = Gst.ElementFactory.make("nveglglessink", "sink") or Gst.ElementFactory.make("autovideosink", "sink")
        sink.set_property("sync", False)

        if not conv or not sink:
            print("Failed to create elements")
        else:
            pipeline.add(conv)
            pipeline.add(sink)

            if not bin.link(conv):
                src_pad = bin.get_static_pad("src")
                sink_pad = conv.get_static_pad("sink")
                if not src_pad or not sink_pad or src_pad.link(sink_pad) != Gst.PadLinkReturn.OK:
                    print("Failed to link source bin to converter")
            if not conv.link(sink):
                print("Failed to link converter to sink")

            loop = GLib.MainLoop()
            bus = pipeline.get_bus()
            bus.add_signal_watch()

            def on_message(bus, message):
                t = message.type
                if t == Gst.MessageType.EOS:
                    print("End-Of-Stream")
                    loop.quit()
                elif t == Gst.MessageType.ERROR:
                    err, dbg = message.parse_error()
                    print(f"Error: {err}: {dbg}")
                    loop.quit()

            bus.connect("message", on_message)

            pipeline.set_state(Gst.State.PLAYING)
            try:
                loop.run()
            except KeyboardInterrupt:
                pass
            pipeline.set_state(Gst.State.NULL)
