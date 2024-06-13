import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GLib

import pyds

NUM_SOURCES = 4

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

def create_source_bin(index, source_id):
    bin_name = f"source-bin-{index}"
    nbin = Gst.Bin.new(bin_name)
    
    source = Gst.ElementFactory.make("videotestsrc", f"source-{index}")
    src_cap = Gst.ElementFactory.make("capsfilter", f"filter-{index}")
    nvconv = Gst.ElementFactory.make("nvvideoconvert", f"nvvideo-converter-{index}")
    conv_cap = Gst.ElementFactory.make("capsfilter", f"filterconv-{index}")

    if not nbin or not source or not src_cap or not nvconv or not conv_cap:
        print("Element could not be created. Exiting.")
        sys.exit(1)

    source.set_property('pattern', source_id)  # Different pattern for each source
    src_caps_prop = Gst.Caps.from_string("video/x-raw, width=1280, height=720, framerate=60/1")
    conv_caps_prop = Gst.Caps.from_string("video/x-raw(memory:NVMM)")

    src_cap.set_property("caps", src_caps_prop)
    conv_cap.set_property("caps", conv_caps_prop)

    nbin.add(source)
    nbin.add(src_cap)
    nbin.add(nvconv)
    nbin.add(conv_cap)

    source.link(src_cap)
    src_cap.link(nvconv)
    nvconv.link(conv_cap)

    bin_pad = Gst.GhostPad.new("src", conv_cap.get_static_pad("src"))
    nbin.add_pad(bin_pad)

    return nbin

# Create a main loop
loop = GLib.MainLoop()

# Create the GStreamer pipeline
pipeline = Gst.Pipeline()

streammux = Gst.ElementFactory.make("nvstreammux", "stream-muxer")
tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "nvvideo-converter")
nvosd = Gst.ElementFactory.make("nvdsosd", "nv-onscreendisplay")
sink = Gst.ElementFactory.make("nveglglessink", "nv-video-renderer")

if not pipeline or not streammux or not tiler or not nvvidconv or not nvosd or not sink:
    print("Element could not be created. Exiting.")
    sys.exit(1)

streammux.set_property('width', 1280)
streammux.set_property('height', 720)
streammux.set_property('batch-size', NUM_SOURCES)
streammux.set_property('batched-push-timeout', 4000000)

tiler.set_property('columns', 2)
tiler.set_property('rows', 2)
tiler.set_property('width', 1920)
tiler.set_property('height', 1080)

nvosd.set_property('process-mode', 1)

# Add elements to the pipeline
pipeline.add(streammux)
pipeline.add(tiler)
pipeline.add(nvvidconv)
pipeline.add(nvosd)
pipeline.add(sink)

# Create and add source bins
source_bins = []
for i in range(NUM_SOURCES):
    source_bin = create_source_bin(i, i)
    source_bins.append(source_bin)
    pipeline.add(source_bin)
    sink_pad = streammux.request_pad_simple(f"sink_{i}")
    src_pad = source_bin.get_static_pad("src")
    src_pad.link(sink_pad)

source_bins[0].set_property('source-id',5)


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
