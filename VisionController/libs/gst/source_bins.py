import sys
import gi
gi.require_version('Gst', '1.0')
# gi.require_version('Aravis', '0.8')
from gi.repository import Gst

import logging
logger = logging.getLogger(__name__)

from ..types import Source, Camera
from ..utils import float_to_fraction

PLACEHOLDER_PATH = "VisionController/data/assets/image_placeholder.png"


def decodebin_child_added(child_proxy, Object, name, user_data):
    logger.debug("Decodebin child added:", name, "\n")
    if name.find("decodebin") != -1:
        Object.connect("child-added", decodebin_child_added, user_data)
    if name.find("nvv4l2decoder") != -1:
        Object.set_property("enable-max-performance", True)
        Object.set_property("drop-frame-interval", 0)
        Object.set_property("num-extra-surfaces", 0)



def cb_newpad(decodebin, pad, data):
    global streammux
    logger.debug("In cb_newpad\n")
    caps = pad.get_current_caps()
    gststruct = caps.get_structure(0)
    gstname = gststruct.get_name()

    if gstname.find("video") != -1:
        source_bin = data
        queue = source_bin.get_by_name("src-queue")

        q_pad = queue.get_static_pad("sink")
        if not q_pad:
            logger.error("Unable to get queue sink pad\n")

        if not pad.link(q_pad) == Gst.PadLinkReturn.OK:
            logger.error("Unable to link decoder src pad to queue sink pad")




def create_uridecodebin_source_bin(index: int, uri: str) -> Gst.Bin:
    logger.debug(f"Creating uridecodebin for {uri}")

    bin_name = f"src-{index}-bin"

    bin = Gst.Bin.new(bin_name)
    if not bin:
        logger.error(" Unable to create bin \n")

    uridecodebin = Gst.ElementFactory.make("uridecodebin", f"source-{index}")
    if not uridecodebin:
        logger.error(" Unable to create uri decode bin \n")


    uridecodebin.set_property("uri", uri)
    uridecodebin.connect("pad-added", cb_newpad, bin)
    uridecodebin.connect("child-added", decodebin_child_added, bin)

    queue = Gst.ElementFactory.make("queue", f"src-queue")
    if not queue:
        logger.error("Unable to create queue for uri decode bin \n")

    queue.set_property("leaky", 1)  # Dropping old buffers
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)

    bin.add(uridecodebin)
    bin.add(queue)


    src_pad = queue.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    # g_source_enabled[index] = True

    return bin


def create_aravis_source_bin(index: int, camera: Camera = None) -> Gst.Bin:
    logger.debug("Creating bin for aravissrc")

    bin_name = f"src{index}-bin"

    ip = camera.ip
    width = camera.width
    height = camera.height
    format = camera.format
    framerate = camera.framerate
    num, denom = float_to_fraction(framerate)
    exposure_time_auto = camera.exposure_time_auto
    exposure_time = camera.exposure_time
    gain_auto = camera.gain_auto
    gain = camera.gain

    bin = Gst.Bin.new(bin_name)
    if not bin:
        logger.error(" Unable to create bin \n")
    
    aravissrc = Gst.ElementFactory.make("aravissrc", f"source-{ip}")
    if not aravissrc:
        logger.error(" Unable to create aravissrc")

    capsfilter_src = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter1")
    if not capsfilter_src:
        logger.error(" Unable to create capsfilter \n")
    
    if format == "BayerRG8":
        caps = Gst.Caps.from_string(f"video/x-bayer,format=rggb,width={width},height={height},binning=1x1, skipping=1x1, framerate={num}/{denom}")
        capsfilter_src.set_property("caps", caps)

        convertor = Gst.ElementFactory.make("tcamconvert", f"src{index}-tcam-convert")
        if not convertor:
            logger.error(" Unable to create tcamconvert element \n")
    else:
        caps = Gst.Caps.from_string(f"video/x-raw,format=(string)RGB8,width={width},height={height},framerate={framerate}/1")
        capsfilter_src.set_property("caps", caps)

        convertor = Gst.ElementFactory.make("videoconvert", f"src{index}-video-converter")
        if not convertor:
            logger.error(" Unable to create videoconvert element \n")

    queue_convertor = Gst.ElementFactory.make("queue", f"src{index}-queue")
    if not queue_convertor:
        logger.error(" Unable to create queue \n")

    # Create the nvvidconv element to convert to NVMM memory
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", f"src{index}-nvvideo-converter")
    if not nvvidconv:
        logger.error(" Unable to create nvvideoconvert element \n")

    # Create the capsfilter element to enforce NVMM memory
    capsfilter2 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter2")
    if not capsfilter2:
        logger.error(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw(memory:NVMM),format=(string)NV12")
    capsfilter2.set_property("caps", caps)

    queue2 = Gst.ElementFactory.make("queue", f"src{index}-queue-out")
    if not queue2:
        logger.error(f"Failed to create src-queue-{index}")


    aravissrc.set_property("exposure-auto", exposure_time_auto) # 0 = Off, 1 = Once, 2 = Continuous
    if exposure_time_auto == 0:
        aravissrc.set_property("exposure", exposure_time)
    aravissrc.set_property("gain-auto", gain_auto) # 0 = Off, 1 = Once, 2 = Continuous
    if gain_auto == 0:
        aravissrc.set_property("gain", gain)
    aravissrc.set_property("num-arv-buffers", 50)
    if camera.type == "TheImagingSource":
        aravissrc.set_property("features", "Zoom=0")

    if ip is not None:
        aravissrc.set_property("camera-name", ip)

    queue_convertor.set_property("leaky", 1)  # Dropping old buffers
    queue_convertor.set_property("max-size-buffers", 1)
    queue_convertor.set_property("max-size-bytes", 0)
    queue_convertor.set_property("max-size-time", 0)

    queue2.set_property("leaky", 1)  # Dropping old buffers
    queue2.set_property("max-size-buffers", 1)
    queue2.set_property("max-size-bytes", 0)
    queue2.set_property("max-size-time", 0)


    bin.add(aravissrc)
    bin.add(capsfilter_src)
    bin.add(queue_convertor)
    bin.add(convertor)
    bin.add(nvvidconv)
    bin.add(capsfilter2)
    bin.add(queue2)


    aravissrc.link(capsfilter_src)
    capsfilter_src.link(queue_convertor)
    queue_convertor.link(convertor)
    convertor.link(nvvidconv)
    nvvidconv.link(capsfilter2)
    capsfilter2.link(queue2)

    src_pad = queue2.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    return bin


def create_tcambin_source_bin(index: int, camera_name: str = None) -> Gst.Bin:
    logger.debug("Creating tcambin")

    bin_name = f"src{index}-bin"

    bin = Gst.Bin.new(bin_name)
    if not bin:
        logger.error(" Unable to create bin \n")
    
    tcambin = Gst.ElementFactory.make("tcambin", f"source-{camera_name}")
    if not tcambin:
        logger.error(" Unable to create tcambin")

    properties = Gst.Structure.new_empty("tcam")
    properties.set_value("exposure-auto", 0)
    properties.set_value("exposure", 10000)
    properties.set_value("gain-auto", 0)
    properties.set_value("gain", 10)
    properties.set_value("num-arv-buffers", 200)
    
    global ip_to_serial
    if camera_name is not None and camera_name in ip_to_serial:
        tcambin.set_property("serial", ip_to_serial[camera_name])
        if camera_name == "10.1.3.75":
            properties.set_value("Zoom", 0)

    tcambin.set_property("tcam-properties", properties)

    device_caps_str = "video/x-bayer,format=rggb,width=1920,height=1080,binning=1x1, skipping=1x1, framerate=54/1"
    tcambin.set_property("device-caps", device_caps_str)
    tcambin.set_property("tcam-properties", properties)


    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "nvvideo-converter")
    if not nvvidconv:
        logger.error(" Unable to create nvvideoconvert element \n")

    capsfilter2 = Gst.ElementFactory.make("capsfilter", "capsfilter2")
    if not capsfilter2:
        logger.error(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw(memory:NVMM),format=(string)NV12")
    capsfilter2.set_property("caps", caps)

    queue = Gst.ElementFactory.make("queue", f"src{index}-queue-out")
    if not queue:
        logger.error(f"Failed to create src-queue-{index}")

    queue.set_property("max-size-time", 0)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-buffers", 1)
    queue.set_property("leaky", 1)
    
    bin.add(tcambin)
    bin.add(nvvidconv)
    bin.add(capsfilter2)
    bin.add(queue)

    tcambin.link(nvvidconv)
    nvvidconv.link(capsfilter2)
    capsfilter2.link(queue)

    src_pad = queue.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    return bin


def create_placeholder_source_bin(index: int) -> Gst.Bin:
    global PLACEHOLDER_PATH
    logger.debug("Creating placeholder bin ")

    bin_name = f"src{index}-bin"

    bin = Gst.Bin.new(bin_name)
    if not bin:
        logger.error(" Unable to create bin \n")

    # Create the source element for reading from the URI
    src_element = Gst.ElementFactory.make("filesrc", f"src{index}-file-source")
    if not src_element:
        logger.error(" Unable to create file source \n")

    src_element.set_property("location", f"{PLACEHOLDER_PATH}")

    # Create the PNG decoder
    png_decoder = Gst.ElementFactory.make("pngdec", f"src{index}-png-decoder")
    if not png_decoder:
        logger.error(" Unable to create png decoder \n")

    videoconvert = Gst.ElementFactory.make("videoconvert", f"src{index}-video-convert")
    if not videoconvert:
        logger.error(" Unable to create videoconvert \n")

    capsfilter1 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter1")
    if not capsfilter1:
        logger.error(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw,format=BGRx")
    capsfilter1.set_property("caps", caps)

    # Create the imagefreeze element
    imagefreeze = Gst.ElementFactory.make("imagefreeze", f"src{index}-image-freeze")
    if not imagefreeze:
        logger.error(" Unable to create imagefreeze element \n")


    capsfilter3 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter3")
    if not capsfilter3:
        logger.error(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw,framerate=200/1")
    capsfilter3.set_property("caps", caps)

    # Create the nvvidconv element to convert to NVMM memory
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", f"src{index}-nvvideo-converter")
    if not nvvidconv:
        logger.error(" Unable to create nvvideoconvert element \n")

    # Create the capsfilter element to enforce NVMM memory
    capsfilter2 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter2")
    if not capsfilter2:
        logger.error(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw(memory:NVMM),format=(string)NV12,width=1920,height=1080")
    capsfilter2.set_property("caps", caps)


    # Create the queue element
    queue = Gst.ElementFactory.make("queue", f"src{index}-queue-out")
    if not queue:
        logger.error("Unable to create queue for placeholder bin \n")


    queue.set_property("leaky", 1)  # Dropping old buffers
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)

    # Add elements to the bin
    bin.add(src_element)
    bin.add(png_decoder)
    bin.add(videoconvert)
    bin.add(capsfilter1)
    bin.add(imagefreeze)
    bin.add(capsfilter3)
    bin.add(nvvidconv)
    bin.add(capsfilter2)
    bin.add(queue)

    # Link the elements
    src_element.link(png_decoder)
    png_decoder.link(videoconvert)
    videoconvert.link(capsfilter1)
    capsfilter1.link(imagefreeze)
    imagefreeze.link(capsfilter3)
    capsfilter3.link(nvvidconv)
    nvvidconv.link(capsfilter2)
    capsfilter2.link(queue)

    # Add the ghost pad
    src_pad = queue.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    # g_source_enabled[index] = True

    return bin


def create_videotestsrc_source_bin(index: int) -> Gst.Bin:
    logger.debug("Creating videotestsrc bin ")

    bin_name = f"src{index}-bin"

    bin = Gst.Bin.new(bin_name)
    if not bin:
        logger.error(" Unable to create bin \n")
    
    videotestsrc = Gst.ElementFactory.make("videotestsrc", f"src{index}-source")
    if not videotestsrc:
        logger.error(" Unable to create videotestsrc \n")

    capsfilter1 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter1")
    if not capsfilter1:
        logger.error(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw,format=(string)BGRx,width=1920,height=1080,framerate=54/1")
    capsfilter1.set_property("caps", caps)


    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", f"src{index}-nvvideoconverter")
    if not nvvidconv:
        logger.error(" Unable to create nvvideoconvert element \n")

    capsfilter2 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter2")
    if not capsfilter2:
        logger.error(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw(memory:NVMM),format=(string)NV12,width=1920,height=1080")
    capsfilter2.set_property("caps", caps)

    queue = Gst.ElementFactory.make("queue", f"src{index}-queue-out")
    if not queue:
        logger.error(f"Failed to create src-queue-{index}")

    queue.set_property("max-size-time", 0)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-buffers", 1)
    queue.set_property("leaky", 1)

    nvvidconv.set_property("nvbuf-memory-type", 0)
    nvvidconv.set_property("gpu-id", 0)

    
    bin.add(videotestsrc)
    bin.add(capsfilter1)
    bin.add(nvvidconv)
    bin.add(capsfilter2)
    bin.add(queue)


    videotestsrc.link(capsfilter1)
    capsfilter1.link(nvvidconv)
    nvvidconv.link(capsfilter2)
    capsfilter2.link(queue)


    src_pad = queue.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    return bin