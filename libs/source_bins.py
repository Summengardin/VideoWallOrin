import sys
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

# sys.path.append('..')
# sys.path.append('../..')

from .types import Source

PLACEHOLDER_PATH = "/home/seaonics/Dev/VideoWallOrin/assets/image_placeholder.png"


def create_uridecodebin_source_bin(g_sources: list[Source], index: int, uri: str) -> Gst.Bin:
    print("Creating uridecodebin for [%s]" % uri)

    g_sources[index].id = index
    bin_name = f"src-{index}-bin"
    print(bin_name)

    bin = Gst.Bin.new(bin_name)
    if not bin:
        sys.stderr.write(" Unable to create bin \n")

    uridecodebin = Gst.ElementFactory.make("uridecodebin", f"src-{index}-uri-decode-bin")
    if not uridecodebin:
        sys.stderr.write(" Unable to create uri decode bin \n")


    uridecodebin.set_property("uri", uri)
    uridecodebin.connect("pad-added", cb_newpad, bin)
    uridecodebin.connect("child-added", decodebin_child_added, bin)

    queue = Gst.ElementFactory.make("queue", f"src-queue")
    if not queue:
        sys.stderr.write("Unable to create queue for uri decode bin \n")

    queue.set_property("leaky", 1)  # Dropping old buffers
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)

    bin.add(uridecodebin)
    bin.add(queue)


    src_pad = queue.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    # g_source_enabled[index] = True

    return g_sources, bin


def create_aravis_source_bin(index: int, camera_name: str = None) -> Gst.Bin:
    print("Creating bin for aravissrc")

    bin_name = f"src{index}-bin"

    bin = Gst.Bin.new(bin_name)
    if not bin:
        sys.stderr.write(" Unable to create bin \n")
    
    aravissrc = Gst.ElementFactory.make("aravissrc", f"source-{camera_name}")
    if not aravissrc:
        sys.stderr.write(" Unable to create aravissrc")

    capsfilter1 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter1")
    if not capsfilter1:
        sys.stderr.write(" Unable to create capsfilter \n")
    
    caps = Gst.Caps.from_string("video/x-bayer,format=rggb,width=1920,height=1080,binning=1x1, skipping=1x1, framerate=54/1")
    capsfilter1.set_property("caps", caps)


    queue = Gst.ElementFactory.make("queue", f"src{index}-queue")
    if not queue:
        sys.stderr.write(" Unable to create queue \n")


    tcamconvert = Gst.ElementFactory.make("tcamconvert", f"src{index}-tcam-convert")
    if not tcamconvert:
        sys.stderr.write(" Unable to create tcamconvert element \n")

    # Create the nvvidconv element to convert to NVMM memory
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", f"src{index}-nvvideo-converter")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvideoconvert element \n")

    # Create the capsfilter element to enforce NVMM memory
    capsfilter2 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter2")
    if not capsfilter2:
        sys.stderr.write(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw(memory:NVMM),format=(string)NV12,width=1920,height=1080")
    capsfilter2.set_property("caps", caps)

    queue2 = Gst.ElementFactory.make("queue", f"src{index}-queue-out")
    if not queue2:
        sys.stderr.write(f"Failed to create src-queue-{index}")


    queue2.set_property("max-size-time", 0)
    queue2.set_property("max-size-bytes", 0)
    queue2.set_property("max-size-buffers", 1)
    queue2.set_property("leaky", 1)


    aravissrc.set_property("exposure-auto", 0) # 0 = Off, 1 = Once, 2 = Continuous
    aravissrc.set_property("exposure", 10000)
    aravissrc.set_property("gain-auto", 0) # 0 = Off, 1 = Once, 2 = Continuous
    aravissrc.set_property("gain", 10)
    aravissrc.set_property("num-arv-buffers", 200)
    if camera_name == "10.1.3.75":
        aravissrc.set_property("features", "Zoom=0")
    elif camera_name == "10.1.3.74":
        aravissrc.set_property("exposure-auto", 0) # 0 = Off, 1 = Once, 2 = Continuous
    aravissrc.set_property("exposure", 20000)
    aravissrc.set_property("gain-auto", 0) # 0 = Off, 1 = Once, 2 = Continuous
    aravissrc.set_property("gain", 1)
    if camera_name is not None:
        aravissrc.set_property("camera-name", camera_name)

    queue.set_property("leaky", 1)  # Dropping old buffers
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)

    queue2.set_property("leaky", 1)  # Dropping old buffers
    queue2.set_property("max-size-buffers", 1)
    queue2.set_property("max-size-bytes", 0)
    queue2.set_property("max-size-time", 0)


    bin.add(aravissrc)
    bin.add(capsfilter1)
    bin.add(queue)
    bin.add(tcamconvert)
    bin.add(nvvidconv)
    bin.add(capsfilter2)
    bin.add(queue2)


    aravissrc.link(capsfilter1)
    capsfilter1.link(queue)
    queue.link(tcamconvert)
    tcamconvert.link(nvvidconv)
    nvvidconv.link(capsfilter2)
    capsfilter2.link(queue2)

    src_pad = queue2.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    return bin


def create_tcambin_source_bin(g_sources: list[Source], index: int, camera_name: str = None) -> Gst.Bin:
    print("Creating tcambin")

    g_sources[index].id = index
    bin_name = f"src{index}-bin"
    print(bin_name)

    bin = Gst.Bin.new(bin_name)
    if not bin:
        sys.stderr.write(" Unable to create bin \n")
    
    tcambin = Gst.ElementFactory.make("tcambin", f"source-{camera_name}")
    if not tcambin:
        sys.stderr.write(" Unable to create tcambin")

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
        sys.stderr.write(" Unable to create nvvideoconvert element \n")

    capsfilter2 = Gst.ElementFactory.make("capsfilter", "capsfilter2")
    if not capsfilter2:
        sys.stderr.write(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw(memory:NVMM),format=(string)NV12")
    capsfilter2.set_property("caps", caps)

    queue = Gst.ElementFactory.make("queue", f"src{index}-queue-out")
    if not queue:
        sys.stderr.write(f"Failed to create src-queue-{index}")

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

    return g_sources, bin


def create_placeholder_source_bin(g_sources: list[Source], index: int) -> Gst.Bin:
    global PLACEHOLDER_PATH
    print("Creating placeholder bin ")

    g_sources[index].id = index
    bin_name = f"src{index}-bin"
    print(bin_name)

    bin = Gst.Bin.new(bin_name)
    if not bin:
        sys.stderr.write(" Unable to create bin \n")

    # Create the source element for reading from the URI
    src_element = Gst.ElementFactory.make("filesrc", f"src{index}-file-source")
    if not src_element:
        sys.stderr.write(" Unable to create file source \n")

    src_element.set_property("location", f"{PLACEHOLDER_PATH}")

    # Create the PNG decoder
    png_decoder = Gst.ElementFactory.make("pngdec", f"src{index}-png-decoder")
    if not png_decoder:
        sys.stderr.write(" Unable to create png decoder \n")

    videoconvert = Gst.ElementFactory.make("videoconvert", f"src{index}-video-convert")
    if not videoconvert:
        sys.stderr.write(" Unable to create videoconvert \n")

    capsfilter1 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter1")
    if not capsfilter1:
        sys.stderr.write(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw,format=BGRx")
    capsfilter1.set_property("caps", caps)

    # Create the imagefreeze element
    imagefreeze = Gst.ElementFactory.make("imagefreeze", f"src{index}-image-freeze")
    if not imagefreeze:
        sys.stderr.write(" Unable to create imagefreeze element \n")


    capsfilter3 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter3")
    if not capsfilter3:
        sys.stderr.write(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw,framerate=54/1")
    capsfilter3.set_property("caps", caps)

    # Create the nvvidconv element to convert to NVMM memory
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", f"src{index}-nvvideo-converter")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvideoconvert element \n")

    # Create the capsfilter element to enforce NVMM memory
    capsfilter2 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter2")
    if not capsfilter2:
        sys.stderr.write(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw(memory:NVMM),format=(string)NV12,width=1920,height=1080")
    capsfilter2.set_property("caps", caps)


    # Create the queue element
    queue = Gst.ElementFactory.make("queue", f"src{index}-queue-out")
    if not queue:
        sys.stderr.write("Unable to create queue for placeholder bin \n")


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

    return g_sources, bin


def create_videotestsrc_source_bin(g_sources: list[Source], index: int) -> Gst.Bin:
    print("Creating videotestsrc bin ")

    g_sources[index].id = index
    bin_name = f"src{index}-bin"
    print(bin_name)

    bin = Gst.Bin.new(bin_name)
    if not bin:
        sys.stderr.write(" Unable to create bin \n")
    
    videotestsrc = Gst.ElementFactory.make("videotestsrc", f"src{index}-source")
    if not videotestsrc:
        sys.stderr.write(" Unable to create videotestsrc \n")

    capsfilter1 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter1")
    if not capsfilter1:
        sys.stderr.write(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw,format=(string)BGRx,width=1920,height=1080,framerate=54/1")
    capsfilter1.set_property("caps", caps)


    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", f"src{index}-nvvideoconverter")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvideoconvert element \n")

    capsfilter2 = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter2")
    if not capsfilter2:
        sys.stderr.write(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw(memory:NVMM),format=(string)NV12,width=1920,height=1080")
    capsfilter2.set_property("caps", caps)

    queue = Gst.ElementFactory.make("queue", f"src{index}-queue-out")
    if not queue:
        sys.stderr.write(f"Failed to create src-queue-{index}")

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

    return g_sources, bin