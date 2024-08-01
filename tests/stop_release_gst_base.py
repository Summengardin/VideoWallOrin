import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import time

# Initialize GStreamer
Gst.init(None)

# Define a function to create and return a new video test source element
def create_video_source(pattern):
    source = Gst.ElementFactory.make('videotestsrc', None)
    source.set_property('pattern', pattern)
    return source

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

# Add elements to the pipeline
pipeline.add(source1)
pipeline.add(videoconvert)
pipeline.add(sink)

# Link elements
source1.link(videoconvert)
videoconvert.link(sink)




# Start playing the pipeline
pipeline.set_state(Gst.State.PLAYING)

Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL , "pipeline_initial")

print("Playing the pipeline...")


# Wait for a while before changing the source
time.sleep(5)

# Remove the old source
pipeline.set_state(Gst.State.PAUSED)
pipeline.remove(source1)


print("Removing the old source...")
time.sleep(5)

Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL , "pipeline_source_removed")

# Create a new source and add it to the pipeline
source2 = create_video_source(1)  # New pattern (snow)
pipeline.add(source2)

# Link the new source to the videoconvert element
source2.link(videoconvert)

print("Adding the new source...")

# Wait for a while before changing the source
time.sleep(5)


Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL , "pipeline_new_source")

# Set the pipeline back to playing state
pipeline.set_state(Gst.State.PLAYING)

# Run the main loop
loop = GLib.MainLoop()
print("Running the main loop...")
try:
    loop.run()
except KeyboardInterrupt:
    pass

# Clean up and stop the pipeline
pipeline.set_state(Gst.State.NULL)
