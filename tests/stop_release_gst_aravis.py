import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import time

ips = ['10.1.3.75', '10.1.3.76']


# Initialize GStreamer
Gst.init(None)

# Define a function to create and return a new video test source element
def create_video_source(index):
    global ips

    bin = Gst.Bin.new("aravis_bin")
    source = Gst.ElementFactory.make('aravissrc', None)
    source.set_property('camera-name', ips[index])
    caps = Gst.Caps.from_string('video/x-raw, width=1920, height=1080')
    capsfilter = Gst.ElementFactory.make('capsfilter', None)
    capsfilter.set_property('caps', caps)

    bin.add(source)
    bin.add(capsfilter)

    source.link(capsfilter)

    pad = capsfilter.get_static_pad('src')
    bin.add_pad(Gst.GhostPad.new('src', pad))

    return bin

# Create the main pipeline
pipeline = Gst.Pipeline.new("test-pipeline")

# Create elements
source1 = create_video_source(0)  # Default pattern (smpte)
videoconvert = Gst.ElementFactory.make('videoconvert', None)
sink = Gst.ElementFactory.make('autovideosink', None)

# Check if elements are created properly
if not pipeline or not source1 or not videoconvert or not sink:
    print("Failed to create elements.")
    exit(1)


sink.set_property("sync", False)

# Add elements to the pipeline
pipeline.add(source1)
pipeline.add(videoconvert)
pipeline.add(sink)

# Link elements
source1.link(videoconvert)
videoconvert.link(sink)



print("Playing the pipeline...")

# Start playing the pipeline
pipeline.set_state(Gst.State.PLAYING)

Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL , "pipeline_initial")




# Wait for a while before changing the source
time.sleep(5)

# Remove the old source
pipeline.set_state(Gst.State.NULL)
pipeline.get_state(Gst.CLOCK_TIME_NONE)

# pipeline.send_event(Gst.Event.new_flush_start())
# pipeline.send_event(Gst.Event.new_flush_stop(True))

time.sleep(1)

print("Removing the old source...")

pipeline.remove(source1)



time.sleep(10)

Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL , "pipeline_source_removed")

print("Adding the new source...")

# Create a new source and add it to the pipeline
source2 = create_video_source(1)  # New pattern (snow)
pipeline.add(source2)

# Link the new source to the videoconvert element
source2.link(videoconvert)



# Wait for a while before changing the source
time.sleep(5)


Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL , "pipeline_new_source")

print("Playing the new source...")


# Set the pipeline back to playing state
pipeline.set_state(Gst.State.PLAYING)
pipeline.get_state(Gst.CLOCK_TIME_NONE)

# Run the main loop

time.sleep(10)

print("Removing the new source...")

# Remove the old source
pipeline.set_state(Gst.State.NULL)
pipeline.get_state(Gst.CLOCK_TIME_NONE)

# pipeline.send_event(Gst.Event.new_flush_start())
# pipeline.send_event(Gst.Event.new_flush_stop(True))

time.sleep(1)

pipeline.remove(source2)

time.sleep(2)

Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL , "pipeline_source_removed")

print("Adding the old source...")

# Create a new source and add it to the pipeline
source3 = create_video_source(0)  # New pattern (snow)
pipeline.add(source3)

# Link the new source to the videoconvert element
source3.link(videoconvert)



# Wait for a while before changing the source
time.sleep(5)

print("Playing the old source...")
Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL , "pipeline_new_source")

# Set the pipeline back to playing state
pipeline.set_state(Gst.State.PLAYING)
pipeline.get_state(Gst.CLOCK_TIME_NONE)

# Run the main loop

loop = GLib.MainLoop()
print("Running the main loop...")
try:
    loop.run()
except KeyboardInterrupt:
    pass

# Clean up and stop the pipeline
pipeline.set_state(Gst.State.NULL)
