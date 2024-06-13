#!/usr/bin/env python3

import sys
sys.path.append('../')
import gi
import configparser
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
from ctypes import *
import time
import math
import random

import pyds

MAX_DISPLAY_LEN = 64
MUXER_OUTPUT_WIDTH = 1920
MUXER_OUTPUT_HEIGHT = 1080
MUXER_BATCH_TIMEOUT_USEC = 33000
TILED_OUTPUT_WIDTH = 1280  
TILED_OUTPUT_HEIGHT = 720
GPU_ID = 0
MAX_NUM_SOURCES = 4
SINK_ELEMENT = "nveglglessink"
PLACEHOLDER_URI =  "file:///home/seaonics/Dev/Samples/assets/image_placeholder.png"

g_num_sources = 0
g_source_id_list = [0] * MAX_NUM_SOURCES
g_eos_list = [False] * MAX_NUM_SOURCES
g_source_enabled = [False] * MAX_NUM_SOURCES
g_source_bin_list = [None] * MAX_NUM_SOURCES

uri_list = ["file:///home/seaonics/Dev/Samples/assets/Sintel.mp4", "file:///home/seaonics/Dev/Samples/assets/image2.mp4", "file:///home/seaonics/Dev/Samples/assets/Big_Buck.mp4"]#,]
cam_uri = "rtsp://192.168.0.14/stream-1.sdp"

loop = None
pipeline = None
streammux = None
sink = None
nvvideoconvert = None
nvosd = None
tiler = None

def decodebin_child_added(child_proxy, Object, name, user_data):
    print("Decodebin child added:", name, "\n")
    if name.find("decodebin") != -1:
        Object.connect("child-added", decodebin_child_added, user_data)
    if name.find("nvv4l2decoder") != -1:
        Object.set_property("enable-max-performance", True)
        Object.set_property("drop-frame-interval", 0)
        Object.set_property("num-extra-surfaces", 0)

def cb_newpad(decodebin, pad, data):
    global streammux
    print("In cb_newpad\n")
    caps = pad.get_current_caps()
    gststruct = caps.get_structure(0)
    gstname = gststruct.get_name()

    print("gstname=", gstname)
    if gstname.find("video") != -1:
        source_bin = data
        queue = source_bin.get_by_name("queue")

        q_pad = queue.get_static_pad("sink")
        if not q_pad:
            sys.stderr.write("Unable to get queue sink pad\n")

        if not pad.link(q_pad) == Gst.PadLinkReturn.OK:
            print("Unable to link decoder src pad to queue sink pad")

def create_uridecode_bin(index, uri):
    global g_source_id_list
    print("Creating uridecodebin for [%s]" % uri)

    g_source_id_list[index] = index
    bin_name = f"source-bin-{g_source_id_list[index]}"
    print(bin_name)

    bin = Gst.Bin.new(bin_name)
    if not bin:
        sys.stderr.write(" Unable to create bin \n")

    uridecodebin = Gst.ElementFactory.make("uridecodebin", "uri-decode-bin")
    if not uridecodebin:
        sys.stderr.write(" Unable to create uri decode bin \n")

    uridecodebin.set_property("uri", uri)
    uridecodebin.connect("pad-added", cb_newpad, bin)
    uridecodebin.connect("child-added", decodebin_child_added, bin)

    queue = Gst.ElementFactory.make("queue", "queue")
    if not queue:
        sys.stderr.write("Unable to create queue for uri decode bin \n")

    queue.set_property("leaky", 2)  # Dropping old buffers
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)

    bin.add(uridecodebin)
    bin.add(queue)


    src_pad = queue.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    

    # g_source_enabled[index] = True

    return bin

def create_placeholder_bin(index):
    global g_source_id_list
    global PLACEHOLDER_URI
    print("Creating placeholder bin ")

    g_source_id_list[index] = index
    bin_name = f"source-bin-placeholder-{g_source_id_list[index]}"
    print(bin_name)

    bin = Gst.Bin.new(bin_name)
    if not bin:
        sys.stderr.write(" Unable to create bin \n")

    # Create the source element for reading from the URI
    src_element = Gst.ElementFactory.make("filesrc", "file-source")
    if not src_element:
        sys.stderr.write(" Unable to create file source \n")

    src_element.set_property("location", PLACEHOLDER_URI.replace("file://", ""))

    # Create the PNG decoder
    png_decoder = Gst.ElementFactory.make("pngdec", "png-decoder")
    if not png_decoder:
        sys.stderr.write(" Unable to create png decoder \n")

    videoconvert = Gst.ElementFactory.make("videoconvert", "video-convert")
    if not videoconvert:
        sys.stderr.write(" Unable to create videoconvert \n")

    capsfilter1 = Gst.ElementFactory.make("capsfilter", "capsfilter1")
    if not capsfilter1:
        sys.stderr.write(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw,format=BGRx")
    capsfilter1.set_property("caps", caps)

    # Create the imagefreeze element
    imagefreeze = Gst.ElementFactory.make("imagefreeze", "image-freeze")
    if not imagefreeze:
        sys.stderr.write(" Unable to create imagefreeze element \n")

    # Create the nvvidconv element to convert to NVMM memory
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "nvvideo-converter")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvideoconvert element \n")

    # Create the capsfilter element to enforce NVMM memory
    capsfilter2 = Gst.ElementFactory.make("capsfilter", "capsfilter2")
    if not capsfilter2:
        sys.stderr.write(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw(memory:NVMM)")
    capsfilter2.set_property("caps", caps)


    # Create the queue element
    queue = Gst.ElementFactory.make("queue", "queue")
    if not queue:
        sys.stderr.write("Unable to create queue for placeholder bin \n")


    queue.set_property("leaky", 2)  # Dropping old buffers
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)

    # Add elements to the bin
    bin.add(src_element)
    bin.add(png_decoder)
    bin.add(videoconvert)
    bin.add(capsfilter1)
    bin.add(imagefreeze)
    bin.add(nvvidconv)
    bin.add(capsfilter2)
    bin.add(queue)

    # Link the elements
    src_element.link(png_decoder)
    png_decoder.link(videoconvert)
    videoconvert.link(capsfilter1)
    capsfilter1.link(imagefreeze)
    imagefreeze.link(nvvidconv)
    nvvidconv.link(capsfilter2)
    capsfilter2.link(queue)

    # Add the ghost pad
    src_pad = queue.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    # g_source_enabled[index] = True

    return bin


def stop_release_source(source_id):
    global g_num_sources
    global g_source_bin_list
    global streammux
    global pipeline

    state_return = g_source_bin_list[source_id].set_state(Gst.State.NULL)

    if state_return == Gst.StateChangeReturn.SUCCESS:
        print("STATE CHANGE SUCCESS\n")
        pad_name = "sink_%u" % source_id
        print(pad_name)
        sinkpad = streammux.get_static_pad(pad_name)
        sinkpad.send_event(Gst.Event.new_flush_stop(False))
        streammux.release_request_pad(sinkpad)
        print("STATE CHANGE SUCCESS\n")
        pipeline.remove(g_source_bin_list[source_id])
        g_num_sources -= 1
        g_source_enabled[source_id] = False
        g_source_bin_list[source_id] = None

    elif state_return == Gst.StateChangeReturn.FAILURE:
        print("STATE CHANGE FAILURE\n")

    elif state_return == Gst.StateChangeReturn.ASYNC:
        state_return = g_source_bin_list[source_id].get_state(Gst.CLOCK_TIME_NONE)
        pad_name = "sink_%u" % source_id
        print(pad_name)
        sinkpad = streammux.get_static_pad(pad_name)
        sinkpad.send_event(Gst.Event.new_flush_stop(False))
        streammux.release_request_pad(sinkpad)
        print("STATE CHANGE ASYNC\n")
        pipeline.remove(g_source_bin_list[source_id])
        g_num_sources -= 1
        g_source_enabled[source_id] = False
        g_source_bin_list[source_id] = None

def delete_sources(data):
    global loop
    global g_num_sources
    global g_eos_list
    global g_source_enabled

    for source_id in range(MAX_NUM_SOURCES):
        if g_eos_list[source_id] and g_source_enabled[source_id]:
            g_source_enabled[source_id] = False
            stop_release_source(source_id)

    if g_num_sources == 0:
        loop.quit()
        print("All sources stopped quitting")
        return False

    source_id = random.randrange(0, MAX_NUM_SOURCES)
    while not g_source_enabled[source_id]:
        source_id = random.randrange(0, MAX_NUM_SOURCES)
    g_source_enabled[source_id] = False
    print("Calling Stop %d " % source_id)
    stop_release_source(source_id)

    if g_num_sources == 0:
        loop.quit()
        print("All sources stopped quitting")
        return False

    return True

def add_source(uri=None, source_id=None):
    global g_num_sources
    global g_source_enabled
    global g_source_bin_list

    global pipeline
    global streammux

    if g_num_sources >= MAX_NUM_SOURCES:
        print("Max number of sources reached. Unable to add source")
        return False

    if source_id is None:
        source_id = g_num_sources

    cnt = 0
    while g_source_enabled[source_id]:
        source_id = (source_id + 1) % MAX_NUM_SOURCES
        cnt += 1
        if cnt > MAX_NUM_SOURCES:
            print("All sources enabled. Exiting")
            print(g_source_enabled)
            return False
        source_id = (source_id + 1) % MAX_NUM_SOURCES

    g_source_enabled[source_id] = True

    if uri is None:
        print("No URI provided. Using placeholder.")
        source_bin = create_placeholder_bin(source_id)
    else:
        print(f"Adding source {source_id} for URI: {uri}")
        source_bin = create_uridecode_bin(source_id, uri)

    if not source_bin:
        sys.stderr.write("Failed to create source bin. Exiting.")
        exit(1)

    g_source_bin_list[source_id] = source_bin
    pipeline.add(source_bin)

    src_pad = source_bin.get_static_pad("src")
    sink_pad = streammux.request_pad_simple(f"sink_{source_id}")
    if src_pad.link(sink_pad) != Gst.PadLinkReturn.OK:
        sys.stderr.write(f"Unable to link source {source_id} to streammux \n")
        return False

    # pipeline_state = pipeline.get_state(Gst.CLOCK_TIME_NONE).state
    # print(f"PIPELINE STATE: {pipeline_state == Gst.State.PLAYING}")

    if pipeline.get_state(Gst.CLOCK_TIME_NONE).state == Gst.State.PLAYING:
        print("PIPELINE IS PLAYING\n")
        state_return = source_bin.set_state(Gst.State.PLAYING)
    
        if state_return == Gst.StateChangeReturn.SUCCESS:
            print("STATE CHANGE SUCCESS\n")
        elif state_return == Gst.StateChangeReturn.FAILURE:
            print("STATE CHANGE FAILURE\n")
            return False
        elif state_return == Gst.StateChangeReturn.ASYNC:
            state_return = g_source_bin_list[source_id].get_state(Gst.CLOCK_TIME_NONE)
        elif state_return == Gst.StateChangeReturn.NO_PREROLL:
            print("STATE CHANGE NO PREROLL\n")

    g_num_sources += 1

    print(f"Added source {source_id} for URI: {uri}")

    return True

def bus_call(bus, message, loop):
    global g_eos_list
    t = message.type
    if t == Gst.MessageType.EOS:
        sys.stdout.write("End-of-stream\n")
        loop.quit()
    elif t == Gst.MessageType.WARNING:
        err, debug = message.parse_warning()
        sys.stderr.write("Warning: %s: %s\n" % (err, debug))
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        sys.stderr.write("Error: %s: %s\n" % (err, debug))
        loop.quit()
    elif t == Gst.MessageType.ELEMENT:
        struct = message.get_structure()
        if struct is not None and struct.has_name("stream-eos"):
            parsed, stream_id = struct.get_uint("stream-id")
            if parsed:
                print("Got EOS from stream %d" % stream_id)
                g_eos_list[stream_id] = True
                stop_release_source(stream_id)
                global g_num_sources, g_source_enabled
                print(f"Number of sources: {g_num_sources}")
                print(g_source_enabled)
                add_source(source_id=stream_id)
                print(f"Number of sources: {g_num_sources}")
    return True


def main(args):
    global g_num_sources
    global g_source_bin_list
    global uri_list

    global loop
    global pipeline
    global streammux
    global sink
    global nvvideoconvert
    global nvosd
    global tiler

    if len(args) < 2:
        sys.stderr.write("Usage: %s <uri> \n" % args[0])
        sys.stderr.write(f"Using defaults instead \n")
    else:
        uri_list = args[1:]

    # num_sources = len(uri_list)

    Gst.init(None)

    print("Creating Pipeline \n ")
    pipeline = Gst.Pipeline()
    is_live = False

    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")
    print("Creating streammux \n ")

    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    if not streammux:
        sys.stderr.write(" Unable to create NvStreamMux \n")

    streammux.set_property("batched-push-timeout", 25000)
    streammux.set_property("batch-size", MAX_NUM_SOURCES)
    streammux.set_property("config-file-path", "/home/seaonics/Dev/Samples/mux_config_source1.txt")

    pipeline.add(streammux)

    # for i in range(num_sources):
    #     print("Creating source_bin ", i, " \n ")
    #     uri = uri_list[i]
    #     if uri.find("rtsp://") == 0:
    #         is_live = True

    #     source_bin = create_uridecode_bin(i, uri)
    #     if not source_bin:
    #         sys.stderr.write("Failed to create source bin. Exiting. \n")
    #         sys.exit(1)
    #     g_source_bin_list[i] = source_bin
    #     pipeline.add(source_bin)
    #     src_pad = source_bin.get_static_pad("src")
    #     sink_pad = streammux.request_pad_simple(f"sink_{i}")
    #     if src_pad.link(sink_pad) != Gst.PadLinkReturn.OK:
    #         sys.stderr.write(f"Unable to link source {i} to streammux \n")


    for i in range(len(uri_list)):
        uri = uri_list[i]
        add_source(uri, i)

    global cam_uri
    add_source(uri=cam_uri)



    # g_num_sources = num_sources

    print("Creating tiler \n ")
    tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
    if not tiler:
        sys.stderr.write(" Unable to create tiler \n")

    print("Creating nvvidconv \n ")
    nvvideoconvert = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    if not nvvideoconvert:
        sys.stderr.write(" Unable to create nvvidconv \n")

    print("Creating nvosd \n ")
    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
    if not nvosd:
        sys.stderr.write(" Unable to create nvosd \n")
        
    print("Creating nv3dsink \n")
    sink = Gst.ElementFactory.make("nv3dsink", "nv3d-sink")
    if not sink:
        sys.stderr.write(" Unable to create nv3dsink \n")

    tiler_rows = 2
    tiler_columns = 2
    tiler.set_property("rows", tiler_rows)
    tiler.set_property("columns", tiler_columns)
    tiler.set_property("width", TILED_OUTPUT_WIDTH)
    tiler.set_property("height", TILED_OUTPUT_HEIGHT)

    tiler.set_property("gpu_id", GPU_ID)
    nvvideoconvert.set_property("gpu_id", GPU_ID)
    nvosd.set_property("gpu_id", GPU_ID)

    print("Adding elements to Pipeline \n")
    pipeline.add(tiler)
    pipeline.add(nvvideoconvert)
    pipeline.add(nvosd)
    pipeline.add(sink)

    print("Linking elements in the Pipeline \n")
    streammux.link(tiler)
    # tiler.link(nvvideoconvert)
    tiler.link(nvosd)
    nvosd.link(sink)

    sink.set_property("sync", 0)
    # sink.set_property("qos", 0)

    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    pipeline.set_state(Gst.State.PAUSED)

    print("Now playing...")
    for i, source in enumerate(uri_list):
        print(i, ": ", source)

    print("Starting pipeline \n")
    pipeline.set_state(Gst.State.PLAYING)

    GLib.timeout_add_seconds(1, add_source, None)
    GLib.timeout_add_seconds(15, add_source, uri_list[0])

    try:
        loop.run()
    except:
        pass

    print("Exiting app\n")
    pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
