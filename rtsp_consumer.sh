#!/bin/bash

uri_default="rtsp://10.0.0.5:8554/test"

uri="${1:-$uri_default}"

# gst-launch-1.0 -v rtspsrc location=${uri} latency=0 ! application/x-rtp, payload=96 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! autovideosink sync=false

# gst-launch-1.0 -v rtspsrc location=${uri} latency=50 ! application/x-rtp, payload=96 ! rtph265depay ! h265parse  ! avdec_h265 ! queue leaky=2 max-size-buffers=1 max-size-bytes=0 max-size-time=0 ! videoconvert ! glimagesink sync=false

# gst-launch-1.0 -v rtspsrc location=${uri} latency=0 ! application/x-rtp, payload=96 ! decodebin ! videoconvert ! autovideosink sync=false

# gst-launch-1.0 -v rtspsrc location=${uri} latency=0 ! application/x-rtp, payload=96 ! rtph265depay ! queue leaky=2 max-size-buffers=1 max-size-bytes=0 max-size-time=0 ! nvv4l2decoder enable-max-performance=1 ! nv3dsink sync=false

gst-launch-1.0 -v uridecodebin uri=${uri} ! nvvideoconvert ! xvimagesink sync=false


# gst-launch-1.0 -v uridecodebin uri=rtsp://192.168.0.14/stream-1.sdp ! nvvideoconvert ! video/x-raw(memory:NVMM) ! nvstreammux ! nvmultistreamtiler ! nvdsosd ! autovideosink sync=false