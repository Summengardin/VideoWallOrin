import logging
logger = logging.getLogger(__name__)
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

PLACEHOLDER_PATH = "VisionController/data/assets/image_placeholder.png"
PLACEHOLDER_URI = "file:///app/VisionController/data/assets/image_placeholder.png"

def create_source_bin(index: int, camera = None) -> Gst.Bin:
    global PLACEHOLDER_PATH
    logger.debug("Creating placeholder bin ")

    bin_name = f"src{index}-bin"

    bin = Gst.Bin.new(bin_name)
    if not bin:
        logger.error(" Unable to create bin \n")

    # Elements
    src_element = Gst.ElementFactory.make("filesrc", f"src{index}-file-source")
    png_decoder = Gst.ElementFactory.make("pngdec", f"src{index}-png-decoder")
    videoconvert = Gst.ElementFactory.make("videoconvert", f"src{index}-video-convert")
    capsfilter1 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter1")
    imagefreeze = Gst.ElementFactory.make("imagefreeze", f"src{index}-image-freeze")
    capsfilter2 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter2")
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", f"src{index}-nvvideo-converter")
    capsfilter3 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter3")
    queue = Gst.ElementFactory.make("queue", f"src{index}-queue-out")

    # filesrc -> pngdec -> videoconvert -> capsfilter1 -> imagefreeze -> capsfilter2 -> nvvidconv -> capsfilter3 -> queue

    # Error checking
    for elem_name, elem in [
        ("filesrc", src_element),
        ("pngdec", png_decoder),
        ("videoconvert", videoconvert),
        ("capsfilter1", capsfilter1),
        ("imagefreeze", imagefreeze),
        ("capsfilter2", capsfilter2),
        ("nvvideoconvert", nvvidconv),
        ("capsfilter3", capsfilter3),
        ("queue", queue)
    ]:
        if not elem:
            logger.error(f"Unable to create {elem_name}")

    # Element settings
    src_element.set_property("location", f"{PLACEHOLDER_PATH}")

    caps1 = Gst.Caps.from_string("video/x-raw,format=BGRx")
    capsfilter1.set_property("caps", caps1)

    imagefreeze.set_property("is-live", True)

    caps2 = Gst.Caps.from_string("video/x-raw,framerate=120/1") 
    capsfilter2.set_property("caps", caps2)

    nvvidconv.set_property("nvbuf-memory-type", 0)
    nvvidconv.set_property("gpu-id", 0)

    caps3 = Gst.Caps.from_string("video/x-raw(memory:NVMM),format=NV12,width=1920,height=1080")
    capsfilter3.set_property("caps", caps3)

    queue.set_property("leaky", 1)
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)

    # Add and link elements
    bin.add(src_element)
    bin.add(png_decoder)
    bin.add(videoconvert)
    bin.add(capsfilter1)
    bin.add(imagefreeze)
    bin.add(capsfilter2)
    bin.add(nvvidconv)
    bin.add(capsfilter3)
    bin.add(queue)

    src_element.link(png_decoder)
    png_decoder.link(videoconvert)
    videoconvert.link(capsfilter1)
    capsfilter1.link(imagefreeze)
    imagefreeze.link(capsfilter2)
    capsfilter2.link(nvvidconv)
    nvvidconv.link(capsfilter3)
    capsfilter3.link(queue)

    # # Trap EOS on filesrc
    # filesrc_pad = src_element.get_static_pad("src")
    # filesrc_pad.add_probe(Gst.PadProbeType.EVENT_DOWNSTREAM, eos_probe_callback)

    # Ghost pad
    src_pad = queue.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    return bin


def eos_probe_callback(pad, info):
    event = info.get_event()
    if event.type == Gst.EventType.EOS:
        logger.debug("Caught EOS on filesrc, dropping it!")
        return Gst.PadProbeReturn.DROP  # Drop EOS event
    return Gst.PadProbeReturn.OK
