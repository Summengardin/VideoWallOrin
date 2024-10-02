import sys
import cv2
import numpy as np
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Initialize GStreamer
Gst.init(None)

# Define RTSP stream URLs
rtsp_streams = [
    'rtsp://10.1.3.71/stream-1.sdp',
    'rtsp://10.1.3.72/stream-1.sdp',
    'rtsp://10.1.3.73/stream-1.sdp',
    'rtsp://10.1.3.74/stream-1.sdp'
    ]

# Create GStreamer pipeline with DeepStream to decode the RTSP streams
def create_rtsp_pipeline(stream_url):
    pipeline_str = (
        f'uridecodebin uri={stream_url} ! '
        'nvvideoconvert ! video/x-raw, format=(string)BGRx ! appsink name=appsink'
    )
    return pipeline_str

# Initialize GStreamer pipelines
pipelines = [Gst.parse_launch(create_rtsp_pipeline(url)) for url in rtsp_streams]

# Start the pipelines
print("Starting pipelines...")
for pipeline in pipelines:
    ret = pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.ASYNC:
        pipeline.get_state(Gst.CLOCK_TIME_NONE)
    

# Function to pull frames from the GStreamer pipeline and display in a 2x2 grid
def display_streams(pipelines):
    # Create a 2x2 grid to display the streams
    grid_size = (2, 2)  # 2 rows, 2 columns

    while True:
        frames = []
        for pipeline in pipelines:
            appsink = pipeline.get_by_name('appsink')
            sample = appsink.emit('pull-sample')
            if sample:
                buf = sample.get_buffer()
                caps = sample.get_caps()
                height = caps.get_structure(0).get_value('height')
                width = caps.get_structure(0).get_value('width')
                arr = np.ndarray(
                    (height, width, 4), buffer=buf.extract_dup(0, buf.get_size()), dtype=np.uint8)
                frames.append(arr)

        if len(frames) == 4:
            # Arrange the frames in a 2x2 grid
            top_row = np.hstack((frames[0], frames[1]))
            bottom_row = np.hstack((frames[2], frames[3]))
            grid_frame = np.vstack((top_row, bottom_row))

            # Show the grid
            cv2.imshow('RTSP Streams (2x2 Grid)', grid_frame)

            # Exit condition
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    # Clean up the pipelines
    for pipeline in pipelines:
        pipeline.set_state(Gst.State.NULL)
    cv2.destroyAllWindows()

# Main execution
if __name__ == '__main__':
    try:
        display_streams(pipelines)
    except KeyboardInterrupt:
        for pipeline in pipelines:
            pipeline.set_state(Gst.State.NULL)
        cv2.destroyAllWindows()
