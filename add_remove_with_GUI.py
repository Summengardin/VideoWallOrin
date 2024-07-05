import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version("Gtk", "4.0")
from gi.repository import Gst, GLib, Gtk
from lib.GUI.GUI import GUI
from lib.utils import index_dataclass
from dataclasses import dataclass 
from enum import Enum
from functools import partial
import sys
import os
import threading



# Initialize GStreamer and GTK
Gst.init(None)
Gtk.init()

class SourceType(Enum):
    DUMMY = 0
    RTSP = 1
    BAYER = 2

@dataclass
class Source:
    id: int = None
    name: str = None
    ip: str = None
    uri: str = None
    type: SourceType = SourceType.DUMMY
    active: bool = False
    bin: Gst.Bin = None
    eos: bool = False


# Define constants
OUTPUT_WIDTH = 3840  
OUTPUT_HEIGHT = 2160
TILER_OUTPUT_ROWS = 2
TILER_OUTPUT_COLS = 2
GPU_ID = 0
MAX_NUM_SOURCES = 4
PLACEHOLDER_IMAGE = "assets/image_placeholder.png"
SINK_ELEMENT = "nv3dsink"
# SINK_ELEMENT = "xvimagesink"
PGIE_CONFIG_FILE = "DeepStream-Yolo/config_infer_primary_yoloV8.txt"



# Global variables
g_num_sources = 0
g_sources = [Source(id=i, name=f"Source {i}") for i in range(MAX_NUM_SOURCES)]
g_add_source_stage = 0
loop = None
pipeline = None
streammux = None
sink = None
nvvideoconvert = None
nvosd = None
tiler = None
pgie = None
gui = None
zoom_level = 0


example_files = ["assets/Sintel.mp4", "assets/image2.mp4", "assets/Big_Buck.mp4"]
cam_name = ""
cam_ips = ["10.1.3.74", "10.1.3.75", "10.1.3.76", "10.1.3.77"]
ip_to_serial = {"10.1.3.74": "40344360",
                "10.1.3.75": "46320531",    
                "10.1.3.76": "40336215",
                "10.1.3.77": "40341020"}



def files_to_uri_list(files):
    cwd = os.getcwd()
    uri_list = [f"file://{cwd}/{file_path}" for file_path in files]

    return uri_list


def set_zoom_level(value):
    global zoom_level, pipeline
    zoom_level = value

    ip = "10.1.3.75"

    tcambin = pipeline.get_by_name(ip)
    properties = tcambin.get_property("tcam-properties")
    properties.set_value("Zoom", zoom_level)
    tcambin.set_property("tcam-properties", properties)


def create_uridecodebin_source_bin(index: int, uri: str) -> Gst.Bin:
    global g_sources
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

    return bin


def create_aravis_source_bin(index: int, camera_name: str = None) -> Gst.Bin:
    global g_sources
    print("Creating bin for aravissrc")

    g_sources[index].id = index
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


def create_tcambin_source_bin(index: int, camera_name: str = None) -> Gst.Bin:
    global g_sources
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

    return bin


def create_placeholder_source_bin(index: int) -> Gst.Bin:
    global g_sources
    global PLACEHOLDER_IMAGE
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

    src_element.set_property("location", f"./{PLACEHOLDER_IMAGE}")

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

    return bin


def create_videotestsrc_source_bin(index: int) -> Gst.Bin:
    global g_sources
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

    return bin


def add_source(uri: str = None, source_id: int = None, camera_name: str = None) -> bool:
    global g_sources
    global g_num_sources
    global pipeline
    global streammux
    global MAX_NUM_SOURCES

    

    # Find available source id
    if source_id is None:
        try:
            source_id = index_dataclass(g_sources, "active", False)
        except Exception as e:
            print("No free source id: ", e)
            return False
        
    if source_id >= MAX_NUM_SOURCES:
        raise IndexError("Source id out of range")

    cnt = 0

    while g_sources[source_id].active:
        source_id = (source_id + 1) % MAX_NUM_SOURCES
        cnt += 1
        if cnt > MAX_NUM_SOURCES:
            print("All sources enabled. Unable to add source")
            return False
        source_id = (source_id + 1) % MAX_NUM_SOURCES

    
    # Remove current source if current is dummy
    if g_sources[source_id].bin is not None and g_sources[source_id].active is False:
        stop_release_source(source_id)


    g_sources[source_id].active = False
    g_sources[source_id].eos = False


    if camera_name is not None:
        print(f"Adding source {source_id} for camera: {camera_name}")
        # if camera_name == "10.1.3.75":
        source_bin = create_aravis_source_bin(source_id, camera_name)
        # else:
            # source_bin = create_aravis_bin(source_id, camera_name)
        g_sources[source_id].active = True
        g_sources[source_id].name = camera_name

    elif uri is not None:
        print(f"Adding source {source_id} for URI: {uri}")
        source_bin = create_uridecodebin_source_bin(source_id, uri)
        g_sources[source_id].active = True
        g_sources[source_id].uri = uri
        g_sources[source_id].name = uri

    else:
        print(f"Adding placeholder at source {source_id}")
        source_bin = create_placeholder_source_bin(source_id)
        g_sources[source_id].name = "placeholder"


    if not source_bin:
        sys.stderr.write("Failed to create source bin. Source not added")
        return False

    g_sources[source_id].bin = source_bin
    pipeline.add(source_bin)
    src_pad = source_bin.get_static_pad("src")
    sink_pad = streammux.request_pad_simple(f"sink_{source_id}")


    if src_pad.link(sink_pad) != Gst.PadLinkReturn.OK:
        sys.stderr.write(f"Unable to link source {source_id} to streammux \n")
        return False

    
    
    if pipeline.get_state(Gst.CLOCK_TIME_NONE).state == Gst.State.PLAYING:
        state_return = source_bin.set_state(Gst.State.PLAYING)
        if state_return == Gst.StateChangeReturn.SUCCESS:
            print("Source added, now playing\n")
        elif state_return == Gst.StateChangeReturn.FAILURE:
            print("Source added, but unable to play\n")
            return False
        elif state_return == Gst.StateChangeReturn.ASYNC:
            state_return = g_sources[source_id].bin.get_state(Gst.CLOCK_TIME_NONE)
        elif state_return == Gst.StateChangeReturn.NO_PREROLL:
            print("STATE CHANGE NO PREROLL\n")

    g_num_sources += 1

    for source in g_sources:
        print(source)

    return True



def stop_release_source(source_id):
    print(f"Stopping and releasing source {source_id} \n")
    global g_num_sources
    global g_source_bin_list
    global streammux
    global pipeline

    if g_sources[source_id].bin is None:
        return

    state_return = g_sources[source_id].bin.set_state(Gst.State.NULL)

    if state_return == Gst.StateChangeReturn.SUCCESS:
        pad_name = "sink_%u" % source_id
        sinkpad = streammux.get_static_pad(pad_name)
        if sinkpad is not None:
            sinkpad.send_event(Gst.Event.new_flush_start())
            sinkpad.send_event(Gst.Event.new_flush_stop(False))
            
            streammux.release_request_pad(sinkpad)

        pipeline.remove(g_sources[source_id].bin)
        g_num_sources -= 1
        g_sources[source_id].active = False
        g_sources[source_id].bin = None 


    elif state_return == Gst.StateChangeReturn.ASYNC:
        state_return = g_source_bin_list[source_id].get_state(Gst.CLOCK_TIME_NONE)
        pad_name = "sink_%u" % source_id
        sinkpad = streammux.get_static_pad(pad_name)
        if sinkpad is not None:
            sinkpad.send_event(Gst.Event.new_flush_stop(False))
            streammux.release_request_pad(sinkpad)

        pipeline.remove(g_source_bin_list[source_id])
        g_num_sources -= 1
        g_sources[source_id].active = False
        g_sources[source_id].bin = None 

    else:
        print("Unable to stop and release source %d" % source_id)


def bus_call(bus, message, loop):
    global g_sources
    global pipeline
    t = message.type

    if t == Gst.MessageType.EOS:
        sys.stdout.write("End-of-stream\n")
        # loop.quit()
    elif t == Gst.MessageType.WARNING:
        err, debug = message.parse_warning()
        sys.stderr.write("Warning: %s: %s\n" % (err, debug))
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        sys.stderr.write("Error: %s: %s\n" % (err, debug))
        # loop.quit()
    elif t == Gst.MessageType.ELEMENT:
        struct = message.get_structure()
        if struct is not None and struct.has_name("stream-eos"):
            parsed, source_id = struct.get_uint("stream-id")
            if parsed:
                print("Got EOS from stream %d" % source_id)
                g_sources[source_id].eos = True
                stop_release_source(source_id)

    return True


def initate_sources():
    for i in range(MAX_NUM_SOURCES):
        add_source(source_id=i)


def main_pipeline():

    global g_num_sources, g_source_bin_list, example_files, uri_list, g_sources
    global loop, pipeline, streammux, sink, nvvideoconvert, nvosd, tiler, pgie

    if len(sys.argv) < 2:
        uri_list = files_to_uri_list(example_files)
    else:
        uri_list = sys.argv[1:]

    print("Creating Pipeline \n")

    pipeline = Gst.Pipeline()
    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")

    print("Creating streammux \n")
    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    if not streammux:
        sys.stderr.write(" Unable to create NvStreamMux \n")

    streammux.set_property("batched-push-timeout", 20000)
    streammux.set_property("batch-size", MAX_NUM_SOURCES)
    streammux.set_property("config-file-path", "./mux_config_source1.txt")
    streammux.set_property("sync-inputs", 0)

    pipeline.add(streammux)

    initate_sources()
    # add_source(camera_name="10.1.3.75", source_id=1)
    # add_source(source_id=2)
    # add_source(camera_name="10.1.3.74")

    print("Creating queue \n")
    queue = Gst.ElementFactory.make("queue", "queue")
    if not queue:
        sys.stderr.write(" Unable to create queue \n")

    print("Creating tiler \n")
    tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
    if not tiler:
        sys.stderr.write(" Unable to create tiler \n")

    print("Creating nvosd \n")
    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
    if not nvosd:
        sys.stderr.write(" Unable to create nvosd \n")

    print("Creating nvvidconv \n")
    nvvideoconvert = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    if not nvvideoconvert:
        sys.stderr.write(" Unable to create nvvidconv \n")

    print(f"Creating {SINK_ELEMENT} \n")
    sink = Gst.ElementFactory.make(SINK_ELEMENT, "sink")
    if not sink:
        sys.stderr.write(" Unable to create sink \n")

    print("Creating fpsdisplaysink \n")
    fps_sink = Gst.ElementFactory.make("fpsdisplaysink", "fps-sink")
    if not fps_sink:
        sys.stderr.write(" Unable to create fps_sink \n")

    queue.set_property("leaky", 1)
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)

    tiler.set_property("rows", TILER_OUTPUT_ROWS)
    tiler.set_property("columns", TILER_OUTPUT_COLS)
    tiler.set_property("width", OUTPUT_WIDTH)
    tiler.set_property("height", OUTPUT_HEIGHT)

    fps_sink.set_property("video-sink", sink)
    fps_sink.set_property("sync", False)
    fps_sink.set_property("text-overlay", False)


    print("Adding elements to Pipeline \n")
    pipeline.add(queue)
    pipeline.add(tiler)
    pipeline.add(nvosd)
    # pipeline.add(nvvideoconvert)
    pipeline.add(fps_sink)

    print("Linking elements in the Pipeline \n")
    streammux.link(queue)
    queue.link(tiler)
    tiler.link(nvosd)
    # nvosd.link(nvvideoconvert)
    nvosd.link(fps_sink)

    loop = GLib.MainLoop()

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    pipeline.set_state(Gst.State.PAUSED)

    print("Now playing...")
    for i, source in enumerate(g_sources):
        print(i, ": ", source.name)
    

    print("Starting pipeline \n")
    state_ret = pipeline.set_state(Gst.State.PLAYING)

    if state_ret == Gst.StateChangeReturn.FAILURE:
        print("Unable to set the pipeline to the playing state")
    
    # try:
    #     _ = index_dataclass(g_sources, "active", True)

    #     print("Starting pipeline \n")
    #     pipeline.set_state(Gst.State.PLAYING)
    # except ValueError:
    #     print("No source is active")
    #     pass

    try:
        print("Running...\n")
        loop.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Loop broke. Exception: {e}\n", exc_info=True)
        pass

    print("Exiting app\n")
    pipeline.set_state(Gst.State.NULL)


def run_pipeline():
    threading.Thread(target=main_pipeline).start()


def cb_add_remove_source(source_id, ip, button, state):
    print(f"\nButton {ip}: {state}\n")
    if state == "On":
        add_source(source_id=source_id, camera_name=ip)
    else:
        stop_release_source(source_id=source_id)

    

def run_gui():
    global gui
    global cam_ips

    labels = cam_ips
    callbacks = [partial(lambda i, button, state: cb_add_remove_source(source_id=i, ip=cam_ips[i], button=button, state=state), i) for i in range(len(cam_ips))]

    gui = GUI(btn_labels=labels, btn_callbacks=callbacks)
    gui.set_callback("zoom", set_zoom_level)

    gui.run()


def main():
    run_pipeline()
    run_gui()

if __name__ == '__main__':
    main()



