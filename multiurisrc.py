import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GLib

import pyds


uri_list = ["file:///home/seaonics/Dev/Samples/assets/Sintel.mp4", "file:///home/seaonics/Dev/Samples/assets/image2.mp4", "file:///home/seaonics/Dev/Samples/assets/Big_Buck.mp4"]#, "file:///home/seaonics/Dev/Samples/image.mp4"]
id_list = [f"source_{i}" for i, _ in enumerate(uri_list)]
NUM_SOURCES = len(uri_list)
print(NUM_SOURCES)
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
        py_nvosd_text_params.font_params.font_size = 10
        py_nvosd_text_params.font_params.font_name =  "Serif"

        # Text background color
        py_nvosd_text_params.set_bg_clr = 1
        py_nvosd_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 1.0)  # Black


        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)

        try:
            l_frame = l_frame.next
        except StopIteration:
            break

    return Gst.PadProbeReturn.OK

def create_multiurisrcbin(uris, ids):
    bin_name = f"source-bin"
    nbin = Gst.Bin.new(bin_name)
    
    source = Gst.ElementFactory.make("nvmultiurisrcbin", f"source")
    if not source:
        print("Element could not be created. Exiting.")
        sys.exit(1)
    
    uris_str = ','.join(uris)
    ids_str  = ','.join(ids)
    source.set_property('uri-list', uris_str)
    source.set_property('sensor-id-list', ids_str)
    # source.set_property('max-batch-size', 4)
    source.set_property('file-loop', 1)
    source.set_property('port', 9000)
    source.set_property('width', 1920)
    source.set_property('height', 1080)
    source.set_property('drop-pipeline-eos', 1)
    source.set_property('live-source', 1)
    source.set_property('config-file-path', "/home/seaonics/Dev/Samples/mux_config_source1.txt")
    # source.set_property('max-latency', 10)

    nbin.add(source)

    bin_pad = Gst.GhostPad.new("src", source.get_static_pad("src"))
    nbin.add_pad(bin_pad)

    return nbin

# Create a main loop
loop = GLib.MainLoop()

# Create the GStreamer pipeline
pipeline = Gst.Pipeline()

# streammux = Gst.ElementFactory.make("nvstreammux", "stream-muxer")
# freeze = Gst.ElementFactory.make("imagefreeze", "freeze")
tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "nvvideo-converter")
nvosd = Gst.ElementFactory.make("nvdsosd", "nv-onscreendisplay")
# sink = Gst.ElementFactory.make("nveglglessink", "nv-video-renderer")
sink = Gst.ElementFactory.make("nv3dsink", "nv-video-renderer")
# sink = Gst.ElementFactory.make("nvoverlaysink", "nv-video-renderer")

if not pipeline or not tiler or not nvvidconv or not nvosd or not sink:
    print("Element could not be created. Exiting.")
    sys.exit(1)

# streammux.set_property('width', 1280)
# streammux.set_property('height', 720)
# streammux.set_property('batch-size', NUM_SOURCES)
# streammux.set_property('batched-push-timeout', 4000000)
# streammux.set_property('num-surfaces-per-frame', NUM_SOURCES)



tiler.set_property('rows', 2)
tiler.set_property('columns', 2)
tiler.set_property('width', 1280)
tiler.set_property('height', 720)
# tiler.set_property('nvbuf-memory-type', 0)
tiler.set_property('show-source', -1) # id of source to preview big.





nvosd.set_property('process-mode', 1)

# Add elements to the pipeline
# pipeline.add(freeze)
pipeline.add(tiler)
pipeline.add(nvvidconv)
pipeline.add(nvosd)
pipeline.add(sink)

# Create and add source bins

source_bin = create_multiurisrcbin(uri_list, id_list)
pipeline.add(source_bin)
# sink_pad = streammux.request_pad_simple(f"sink_0")
# src_pad = source_bin.get_static_pad("src")
# src_pad.link(sink_pad)

# Link the remaining elements
if not source_bin.link(tiler):
    print("ERROR: Could not link source-bin to tiler")
    sys.exit(1)

# if not freeze.link(tiler):
#     print("ERROR: Could not link source-bin to tiler")
#     sys.exit(1)

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
