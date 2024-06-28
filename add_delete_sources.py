#!/usr/bin/env python3

import sys
sys.path.append('../')
import gi
import os
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GLib
from ctypes import *
import time
import math
import random

import pyds

TILED_OUTPUT_WIDTH = 3840  
TILED_OUTPUT_HEIGHT = 2160
TILED_OUTPUT_ROWS = 2
TILED_OUTPUT_COLS = 2
GPU_ID = 0
MAX_NUM_SOURCES = 4
PLACEHOLDER_IMAGE = "assets/image_placeholder.png"
SINK_ELEMENT = "nv3dsink"

PGIE_CONFIG_FILE = "DeepStream-Yolo/config_infer_primary_yoloV8.txt"
# PGIE_CONFIG_FILE  = "/home/seaonics/Dev/VideoWallOrin/config/dstest_pgie_config.txt"
PGIE_CLASS_ID_VEHICLE = 0
PGIE_CLASS_ID_BICYCLE = 1
PGIE_CLASS_ID_PERSON = 2
PGIE_CLASS_ID_ROADSIGN = 3

g_num_sources = 0
g_source_id_list = [0] * MAX_NUM_SOURCES
g_eos_list = [False] * MAX_NUM_SOURCES
g_source_enabled = [False] * MAX_NUM_SOURCES
g_source_bin_list = [None] * MAX_NUM_SOURCES

example_files = ["assets/Sintel.mp4", "assets/image2.mp4", "assets/Big_Buck.mp4"]
# uri_list = ["file://assets/Sintel.mp4", "file:///home/seaonics/Dev/Samples/assets/image2.mp4", "file:///home/seaonics/Dev/Samples/assets/Big_Buck.mp4"]#,]
cam_uri = "rtsp://192.168.0.14/stream-1.sdp"
cam_name = ""
cam_ips = ["10.1.3.75", "10.1.3.74"]


ip_to_serial = {"10.1.3.75": "46320531", "10.1.3.74": "40344360" }



zoom_level = 0

loop = None
pipeline = None
streammux = None
sink = None
nvvideoconvert = None
nvosd = None
tiler = None
pgie = None

pgie_classes_str= ["Vehicle", "TwoWheeler", "Person","RoadSign"]


def files_to_uri_list(files):
    cwd = os.getcwd()
    uri_list = [f"file://{cwd}/{file_path}" for file_path in files]

    return uri_list


'''def osd_sink_pad_buffer_probe(pad, info, u_data):
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer")
        return Gst.PadProbeReturn.OK

    # Retrieve batch metadata from the gst_buffer
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    # print(f"Number of frames {batch_meta.frame_meta_pool.num_full_elements}")
    l_frame = batch_meta.frame_meta_list
    while l_frame is not None:
        try:
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break


        display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
        display_meta.num_labels = 1
        py_nvosd_text_params = display_meta.text_params[0]

        
        py_nvosd_text_params.display_text = f"Stream {frame_meta.source_id}  Resolution: {frame_meta.source_frame_width}x{frame_meta.source_frame_height}"
        # py_nvosd_text_params.display_text = f"Stream   Resolution: {frame_meta.source_frame_width}x{frame_meta.source_frame_height}"


        # Set text location
        py_nvosd_text_params.x_offset = 10
        py_nvosd_text_params.y_offset = 10

        # Display text color
        py_nvosd_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)  # White
        py_nvosd_text_params.font_params.font_size = 24
        py_nvosd_text_params.font_params.font_name =  "Serif"

        # Text background color
        py_nvosd_text_params.set_bg_clr = 1
        py_nvosd_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 1.0)  # Black


        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)

        try:
            l_frame = l_frame.next
        except StopIteration:
            break

    return Gst.PadProbeReturn.OK'''

PGIE_CLASS_ID_VEHICLE = 0
PGIE_CLASS_ID_BICYCLE = 1
PGIE_CLASS_ID_PERSON = 2
PGIE_CLASS_ID_ROADSIGN = 3

def osd_sink_pad_buffer_probe(pad,info,u_data):
    return Gst.PadProbeReturn.OK
    frame_number=0
    num_rects=0

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    # Retrieve batch metadata from the gst_buffer
    # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
    # C address of gst_buffer as input, which is obtained with hash(gst_buffer)
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list
    while l_frame is not None:
        try:
            # Note that l_frame.data needs a cast to pyds.NvDsFrameMeta
            # The casting is done by pyds.NvDsFrameMeta.cast()
            # The casting also keeps ownership of the underlying memory
            # in the C code, so the Python garbage collector will leave
            # it alone.
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break

        #Intiallizing object counter with 0.
        obj_counter = {
            PGIE_CLASS_ID_VEHICLE:0,
            PGIE_CLASS_ID_PERSON:0,
            PGIE_CLASS_ID_BICYCLE:0,
            PGIE_CLASS_ID_ROADSIGN:0
        }
        frame_number=frame_meta.frame_num
        num_rects = frame_meta.num_obj_meta
        l_obj=frame_meta.obj_meta_list
        while l_obj is not None:
            try:
                # Casting l_obj.data to pyds.NvDsObjectMeta
                obj_meta=pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                break
            obj_counter[obj_meta.class_id] += 1
            obj_meta.rect_params.border_color.set(0.0, 0.0, 1.0, 0.8) #0.8 is alpha (opacity)
            try: 
                l_obj=l_obj.next
            except StopIteration:
                break

        # Acquiring a display meta object. The memory ownership remains in
        # the C code so downstream plugins can still access it. Otherwise
        # the garbage collector will claim it when this probe function exits.
        display_meta=pyds.nvds_acquire_display_meta_from_pool(batch_meta)
        display_meta.num_labels = 1
        py_nvosd_text_params = display_meta.text_params[0]
        # Setting display text to be shown on screen
        # Note that the pyds module allocates a buffer for the string, and the
        # memory will not be claimed by the garbage collector.
        # Reading the display_text field here will return the C address of the
        # allocated string. Use pyds.get_string() to get the string content.
        py_nvosd_text_params.display_text = "Frame Number={} Number of Objects={} Vehicle_count={} Person_count={}".format(frame_number, num_rects, obj_counter[PGIE_CLASS_ID_VEHICLE], obj_counter[PGIE_CLASS_ID_PERSON])

        # Now set the offsets where the string should appear
        py_nvosd_text_params.x_offset = 10
        py_nvosd_text_params.y_offset = 12

        # Font , font-color and font-size
        py_nvosd_text_params.font_params.font_name = "Serif"
        py_nvosd_text_params.font_params.font_size = 10
        # set(red, green, blue, alpha); set to White
        py_nvosd_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)

        # Text background color
        py_nvosd_text_params.set_bg_clr = 1
        # set(red, green, blue, alpha); set to Black
        py_nvosd_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 1.0)
        # Using pyds.get_string() to get display_text as string
        print(pyds.get_string(py_nvosd_text_params.display_text))
        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
        try:
            l_frame=l_frame.next
        except StopIteration:
            break
			
    return Gst.PadProbeReturn.OK	



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



def create_uridecode_bin(index:int, uri:str):
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



def create_aravis_bin_(index:int, camera_name: str=None):
    global g_source_id_list
    print("Creating bin for aravissrc")

    g_source_id_list[index] = index
    bin_name = f"source-bin-{g_source_id_list[index]}"
    print(bin_name)

    bin = Gst.Bin.new(bin_name)
    if not bin:
        sys.stderr.write(" Unable to create bin \n")
    
    aravissrc = Gst.ElementFactory.make("aravissrc", f"{camera_name}")
    if not aravissrc:
        sys.stderr.write(" Unable to create aravissrc")

    capsfilter1 = Gst.ElementFactory.make("capsfilter", "capsfilter1")
    if not capsfilter1:
        sys.stderr.write(" Unable to create capsfilter \n")
    
    caps = Gst.Caps.from_string("video/x-bayer,format=rggb,width=1920,height=1080,binning=1x1, skipping=1x1, framerate=54/1")
    capsfilter1.set_property("caps", caps)


    queue = Gst.ElementFactory.make("queue", "queue")
    if not queue:
        sys.stderr.write(" Unable to create queue \n")


    tcamconvert = Gst.ElementFactory.make("tcamconvert", "tcam-convert")
    if not tcamconvert:
        sys.stderr.write(" Unable to create tcamconvert element \n")

    # Create the nvvidconv element to convert to NVMM memory
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "nvvideo-converter")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvideoconvert element \n")

    # Create the capsfilter element to enforce NVMM memory
    capsfilter2 = Gst.ElementFactory.make("capsfilter", "capsfilter2")
    if not capsfilter2:
        sys.stderr.write(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw(memory:NVMM),format=NV12")
    capsfilter2.set_property("caps", caps)

    aravissrc.set_property("exposure-auto", 0) # 0 = Off, 1 = Once, 2 = Continuous
    aravissrc.set_property("exposure", 10000)
    aravissrc.set_property("gain-auto", 0) # 0 = Off, 1 = Once, 2 = Continuous
    aravissrc.set_property("gain", 10)
    aravissrc.set_property("num-arv-buffers", 200)
    if camera_name == "10.1.3.75":
        aravissrc.set_property("features", "Zoom=500")
    if camera_name is not None:
        aravissrc.set_property("camera-name", camera_name)

    queue.set_property("leaky", 1)  # Dropping old buffers
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)

    bin.add(aravissrc)
    bin.add(capsfilter1)
    bin.add(queue)
    bin.add(tcamconvert)
    bin.add(nvvidconv)
    bin.add(capsfilter2)

    aravissrc.link(capsfilter1)
    capsfilter1.link(queue)
    queue.link(tcamconvert)
    tcamconvert.link(nvvidconv)
    nvvidconv.link(capsfilter2)

    src_pad = capsfilter2.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    return bin



def create_aravis_bin(index:int, camera_name: str=None):
    global g_source_id_list
    print("Creating tcambin")

    g_source_id_list[index] = index
    bin_name = f"source-bin-{g_source_id_list[index]}"
    print(bin_name)

    bin = Gst.Bin.new(bin_name)
    if not bin:
        sys.stderr.write(" Unable to create bin \n")
    
    tcambin = Gst.ElementFactory.make("tcambin", f"{camera_name}")
    if not tcambin:
        sys.stderr.write(" Unable to create aravissrc")

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


    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "nvvideo-converter")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvideoconvert element \n")

    capsfilter2 = Gst.ElementFactory.make("capsfilter", "capsfilter2")
    if not capsfilter2:
        sys.stderr.write(" Unable to create capsfilter element \n")

    caps = Gst.Caps.from_string("video/x-raw(memory:NVMM),format=(string)NV12")
    capsfilter2.set_property("caps", caps)

    
    bin.add(tcambin)
    bin.add(nvvidconv)
    bin.add(capsfilter2)

    tcambin.link(nvvidconv)
    nvvidconv.link(capsfilter2)

    src_pad = capsfilter2.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    return bin



def create_placeholder_bin(index:int):
    global g_source_id_list
    global PLACEHOLDER_IMAGE
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

    src_element.set_property("location", f"./{PLACEHOLDER_IMAGE}")

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



def zoom_(ip: str):
    global pipeline
    global zoom_level

    if zoom_level < 1000:
        zoom_level += 1
    else:
        zoom_level = 0

    source_element = pipeline.get_by_name(ip) # type=GstAravis
    for met in dir(source_element):
        print(met)
    source_element.set_property("features", f"Zoom={zoom_level}")
    print(f"features: {source_element.get_property('features')}")
    # source_element.set_property("features", f"Zoom={zoom_level}") # type=String
    # camera.set_property("Zoom", new_zoom_level)
    return True



def zoom(ip: str):
    global pipeline
    global zoom_level

    if zoom_level < 1000:
        zoom_level += 1
    else:
        zoom_level = 0

    tcambin = pipeline.get_by_name(ip)
    properties = tcambin.get_property("tcam-properties")
    # print(f"Current Zoom: {properties.get_value('Zoom')}")
    properties.set_value("Zoom", zoom_level)
    # print(f"New Zoom: {properties.get_value('Zoom')}")
    tcambin.set_property("tcam-properties", properties)

    return True



def add_source(uri=None, source_id=None, camera_name=None):
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
            print("All sources enabled. Unale to add source")
            print(g_source_enabled)
            return False
        source_id = (source_id + 1) % MAX_NUM_SOURCES

    g_source_enabled[source_id] = True

    if camera_name is not None:
        print(f"Adding source {source_id} for camera: {camera_name}")
        print(f"DEBUG: camera name supplied, suggested using aravissrc")
        source_bin = create_aravis_bin(source_id, camera_name)
    elif uri is not None:
        print(f"Adding source {source_id} for URI: {uri}")
        source_bin = create_uridecode_bin(source_id, uri)
    else:
        print(f"Adding placeholder at source {source_id}")
        source_bin = create_placeholder_bin(source_id)

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


    Gst.debug_bin_to_dot_file(source_bin, Gst.DebugGraphDetails.ALL, f"source-bin-{source_id}")

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
    global example_files
    global uri_list

    global loop
    global pipeline
    global streammux
    global sink
    global nvvideoconvert
    global nvosd
    global tiler
    global pgie

    if len(args) < 2:
        sys.stderr.write("Usage: %s <uri> \n" % args[0])
        sys.stderr.write(f"Using defaults instead \n")
        
        uri_list = files_to_uri_list(example_files)
    else:
        uri_list = args[1:]

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

    streammux.set_property("batched-push-timeout", 20000)
    streammux.set_property("batch-size", MAX_NUM_SOURCES)
    streammux.set_property("config-file-path", "/home/seaonics/Dev/Samples/mux_config_source1.txt")

    pipeline.add(streammux)

    # for i in range(len(uri_list)):
    #     uri = uri_list[i]
    #     add_source(uri, i)

    # global cam_uri
    # add_source(uri=cam_uri, source_id=3)

    global cam_name
    cam_name = "10.1.3.75"
    add_source(camera_name=cam_name, source_id=3)


    # global cam_ips
    # for i in range(len(cam_ips)):
    #     add_source(camera_name=cam_ips[i], source_id=i*2)
    



    # g_num_sources = num_sources




    print("Creating queue \n ")
    queue = Gst.ElementFactory.make("queue", "queue")
    if not queue:
        sys.stderr.write(" Unable to create queue \n")

    print("Creating pgie \n ")
    pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
    if not pgie:
        sys.stderr.write(" Unable to create pgie \n")

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
        
    print(f"Creating {SINK_ELEMENT} \n")
    sink = Gst.ElementFactory.make(SINK_ELEMENT, "sink")
    if not sink:
        sys.stderr.write(" Unable to create sink \n")


    queue.set_property("leaky", 1)
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)


    pgie.set_property('config-file-path', PGIE_CONFIG_FILE)
    pgie_batch_size=pgie.get_property("batch-size")
    if(pgie_batch_size < MAX_NUM_SOURCES):
        print("WARNING: Overriding infer-config batch-size",pgie_batch_size," with number of sources ", g_num_sources," \n")
    pgie.set_property("batch-size",MAX_NUM_SOURCES)

    pgie.set_property("gpu_id", GPU_ID)

    # tiler.set_property("compute-hw", 2)
    tiler.set_property("rows", TILED_OUTPUT_ROWS)
    tiler.set_property("columns", TILED_OUTPUT_COLS)
    tiler.set_property("width", TILED_OUTPUT_WIDTH)
    tiler.set_property("height", TILED_OUTPUT_HEIGHT)
    # tiler.set_property("compute-hw", 2)

    # nvvideoconvert.s et_property("compute-hw", 2)


    sink.set_property("sync", 0)
    # sink.set_property("qos", 0)
    # sink.set_property("plane-id", 2)
    # sink.set_property("window-x", 0)
    # sink.set_property("window-y", 0)
    # sink.set_property("window-width", TILED_OUTPUT_WIDTH)
    # sink.set_property("window-height", TILED_OUTPUT_HEIGHT)
    # sink.set_property("processing-deadline", 0)


    # videoconvert = Gst.ElementFactory.make("videoconvert", "videoconvert")

    print("Adding elements to Pipeline \n")
    pipeline.add(queue)
    pipeline.add(tiler)
    pipeline.add(nvosd)
    # pipeline.add(nvvideoconvert)
    # pipeline.add(videoconvert)
    pipeline.add(sink)
    # pipeline.add(pgie)

    print("Linking elements in the Pipeline \n")
    streammux.link(queue)
    queue.link(tiler)
    # pgie.link(tiler)
    tiler.link(nvosd)
    # tiler.link(nvosd)
    nvosd.link(sink)
    # videoconvert.link(sink)
    # queue.link(sink)



    osdsinkpad = tiler.get_static_pad("sink")
    if not osdsinkpad:
        print("Unable to get sink pad")
    else:
        osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)
    

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

    # GLib.timeout_add_seconds(1, add_source, None)
    # GLib.timeout_add_seconds(15, add_source, uri_list[0])
    GLib.timeout_add(1, zoom, "10.1.3.75")


    Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL, "add_delete_sources")

    try: 
        print("Running...\n")
        loop.run()
    except:
        pass

    print("Exiting app\n")
    pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
