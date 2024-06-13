import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GLib

import pyds

NUM_SOURCES = 2

# Initialize GStreamer
Gst.init(None)

# Function to handle messages from the GStreamer bus
def bus_call(bus, message, loop):
    msg_type = message.type
    if msg_type == Gst.MessageType.EOS:
        print("End of stream")
        loop.quit()
    elif msg_type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print("Error: %s: %s" % (err, debug))
        loop.quit()
    return True

# Function to add text over each stream
def osd_sink_pad_buffer_probe(pad, info, u_data):
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer")
        return Gst.PadProbeReturn.OK
    
    print(gst_buffer.n_memory())

    # Retrieve batch metadata from the gst_buffer
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list
    while l_frame is not None:
        try:
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break

        # Add OSD text for each stream
        display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
        display_meta.num_labels = 1
        py_nvosd_text_params = display_meta.text_params[0]
        py_nvosd_text_params.display_text = f"Stream: {frame_meta.pad_index} Width: {frame_meta.source_frame_width} Height: {frame_meta.source_frame_height}"

        # Set text location
        py_nvosd_text_params.x_offset = 10
        py_nvosd_text_params.y_offset = 12

        # Display text color
        py_nvosd_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)  # White
        py_nvosd_text_params.font_params.font_size = 12
        py_nvosd_text_params.font_params.font_name = "Serif"

        # Text background color
        py_nvosd_text_params.set_bg_clr = 1
        py_nvosd_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 1.0)  # Black

        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)

        try:
            l_frame = l_frame.next
        except StopIteration:
            break

    return Gst.PadProbeReturn.OK

# Create a main loop
loop = GLib.MainLoop()

# Create the GStreamer pipeline
pipeline = Gst.Pipeline()

# Create elements
source1 = Gst.ElementFactory.make("videotestsrc", "source1")
source2 = Gst.ElementFactory.make("videotestsrc", "source2")
src1_caps = Gst.ElementFactory.make("capsfilter", "filter1")
src2_caps = Gst.ElementFactory.make("capsfilter", "filter2")
nvconv1 = Gst.ElementFactory.make("nvvideoconvert", "nvvideo-converter-s1")
nvconv2 = Gst.ElementFactory.make("nvvideoconvert", "nvvideo-converter-s2")
conv1_caps = Gst.ElementFactory.make("capsfilter", "filterconv1")
conv2_caps = Gst.ElementFactory.make("capsfilter", "filterconv2")
streammux = Gst.ElementFactory.make("nvstreammux", "stream-muxer")
tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "nvvideo-converter")
nvosd = Gst.ElementFactory.make("nvdsosd", "nv-onscreendisplay")
sink = Gst.ElementFactory.make("nveglglessink", "nv-video-renderer")

if not pipeline or not source1 or not source2 or not streammux or not tiler or not nvvidconv or not nvosd or not sink:
    print("Element could not be created. Exiting.")
    sys.exit(1)

# Set properties for elements
source1.set_property('pattern', 0)  # Pattern 0 for source1
source2.set_property('pattern', 1)  # Pattern 1 for source2

src_caps = Gst.Caps.from_string("video/x-raw, width=1280, height=720, framerate=60/1")
src1_caps.set_property("caps", src_caps)
src2_caps.set_property("caps", src_caps)

conv_caps = Gst.Caps.from_string("video/x-raw(memory:NVMM)")
conv1_caps.set_property("caps", conv_caps)
conv2_caps.set_property("caps", conv_caps)

streammux.set_property('width', 1280)
streammux.set_property('height', 720)
streammux.set_property('batch-size', 2)
streammux.set_property('batched-push-timeout', 4000000)

tiler.set_property('rows', 2)
tiler.set_property('columns', 2)
tiler.set_property('width', 1920)
tiler.set_property('height', 1080)

nvosd.set_property('process-mode', 1)

# Add elements to the pipeline
pipeline.add(source1)
pipeline.add(source2)
pipeline.add(src1_caps)
pipeline.add(src2_caps)
pipeline.add(nvconv1)
pipeline.add(nvconv2)
pipeline.add(conv1_caps)
pipeline.add(conv2_caps)
pipeline.add(streammux)
pipeline.add(tiler)
pipeline.add(nvvidconv)
pipeline.add(nvosd)
pipeline.add(sink)

# Link the elements together
# if not source1.link(capsfilter1):
#     print("ERROR: Could not link source1 to capsfilter1")
#     sys.exit(1)

# if not source2.link(capsfilter2):
#     print("ERROR: Could not link source2 to capsfilter2")
    # sys.exit(1)



if not source1.link(src1_caps):
    print("ERROR: Could not link source1 to capsfilter.")
    sys.exit(1)
if not source2.link(src2_caps):
    print("ERROR: Could not link source2 to capsfilter.")
    sys.exit(1)


if not src1_caps.link(nvconv1):
    print("ERROR: Could not link src_caps to nvconv1")
    sys.exit(1)
if not src2_caps.link(nvconv2):
    print("ERROR: Could not link src_caps to nvconv2")
    sys.exit(1)

if not nvconv1.link(conv1_caps):
    print("ERROR: Could not link nvconv1 to conv_caps")
    sys.exit(1)
if not nvconv2.link(conv2_caps):
    print("ERROR: Could not link nvconv2 to conv_caps")
    sys.exit(1)



source1_srcpad = conv1_caps.get_static_pad("src")
if not source1_srcpad:
    print("Unable to get the src pad from capsfilter1")
    sys.exit(1)
source2_srcpad = conv2_caps.get_static_pad("src")
if not source2_srcpad:
    print("Unable to get the src pad from capsfilter2")
    sys.exit(1)

sinkpad1 = streammux.request_pad_simple("sink_0")
if not sinkpad1:
    print("Unable to get the sink1 pad")
    sys.exit(1)

sinkpad2 = streammux.request_pad_simple("sink_1")
if not sinkpad2:
    print("Unable to get the sink2 pad")
    sys.exit(1)

source1_srcpad.link(sinkpad1)
source2_srcpad.link(sinkpad2)

# Link the remaining elements
if not streammux.link(tiler):
    print("ERROR: Could not link streammux to tiler")
    sys.exit(1)

if not tiler.link(nvvidconv):
    print("ERROR: Could not link tiler to nvvidconv")
    sys.exit(1)

if not nvvidconv.link(nvosd):
    print("ERROR: Could not link nvvidconv to nvosd")
    sys.exit(1)

if not nvosd.link(sink):
    print("ERROR: Could not link nvosd to sink")
    sys.exit(1)


# Add a probe to the OSD sink pad to add text over the streams
osdsinkpad = tiler.get_static_pad("sink")
if not osdsinkpad:
    print("Unable to get sink pad")
else:
    osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)

# Create and start the GStreamer bus
bus = pipeline.get_bus()
bus.add_signal_watch()
bus.connect("message", bus_call, loop)

# Start the pipeline
pipeline.set_state(Gst.State.PLAYING)

# Start the main loop
try:
    loop.run()
except:
    pass

# Clean up
pipeline.set_state(Gst.State.NULL)
