import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, GLib
import sys

# Initialize GStreamer
Gst.init(None)

# Create the pipeline
pipeline = Gst.Pipeline.new("rtsp-pipeline")

# Create elements
source = Gst.ElementFactory.make("uridecodebin", "source")
if not source:
    print("Could not create 'uridecodebin' element.")
    sys.exit(1)

sink = Gst.ElementFactory.make("nv3dsink", "sink")
if not sink:
    print("Could not create 'nv3dsink' element.")
    sys.exit(1)
sink.set_property('sync', False)

# Set the RTSP URI
source.set_property('uri', 'rtsp://10.1.3.71/stream-1.sdp')

# Add elements to the pipeline
pipeline.add(source)
pipeline.add(sink)

# Link the elements when the pad is added
def on_pad_added(src, pad):
    print("New pad '{}' added.".format(pad.get_name()))
    sink_pad = sink.get_static_pad("sink")
    if not sink_pad.is_linked():
        pad.link(sink_pad)

source.connect("pad-added", on_pad_added)

# Function to remove the source from the pipeline
def remove_source():
    print("Removing source from pipeline.")
    pipeline.set_state(Gst.State.NULL)
    pipeline.remove(source)
    source.set_state(Gst.State.NULL)
    return False  # Don't call this function again

# Function to add the source back to the pipeline
def add_source():
    print("Adding source back to pipeline.")
    pipeline.add(source)
    source.set_state(Gst.State.PLAYING)
    source.connect("pad-added", on_pad_added)
    pipeline.set_state(Gst.State.PLAYING)
    return False  # Don't call this function again

# Schedule the removal and addition of the source
GLib.timeout_add_seconds(5, remove_source)  # Remove after 10 seconds
GLib.timeout_add_seconds(10, add_source)     # Add back after 5 more seconds

# Start playing the pipeline
pipeline.set_state(Gst.State.PLAYING)

# Run the GLib main loop
loop = GLib.MainLoop()

# Add a bus to handle messages
bus = pipeline.get_bus()
bus.add_signal_watch()

def on_message(bus, message):
    msg_type = message.type
    if msg_type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print("Error: {}".format(err), debug)
        loop.quit()
    elif msg_type == Gst.MessageType.EOS:
        print("End of stream")
        loop.quit()

bus.connect("message", on_message)

try:
    loop.run()
except KeyboardInterrupt:
    pass
finally:
    # Clean up
    pipeline.set_state(Gst.State.NULL)
