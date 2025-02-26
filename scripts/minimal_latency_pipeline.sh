#!/bin/bash

# Example usage: bash display.sh camera-rgb 0

cam_default="10.1.3.75"
dbg_default="0"

cam="${1:-$cam_default}"

dbg="${2:-$dbg_default}"


if [ $cam == "10.1.3.75" ]; then
    gst-launch-1.0 aravissrc camera-name=$cam ! video/x-bayer,width=1920,height=1080,framerate=54/1,format=rggb ! tcamconvert ! videoconvert ! xvimagesink sync=false
elif [ $cam == "10.1.3.74" ] || [ $cam == "10.1.3.76" ] || [ $cam == "10.1.3.77" ]; then
    gst-launch-1.0 aravissrc camera-name=$cam ! video/x-bayer,width=1920,height=1080,framerate=100/1,format=rggb ! tcamconvert ! videoconvert ! xvimagesink sync=false
elif [ $cam == "192.168.0.90" ]; then
    gst-launch-1.0 uridecodebin uri=rtsp://$cam/axis-media/media.amp?streamprofile=stream-1 caps="video/x-raw(memory:NVMM), width=1920, height=1080, format=NV12" ! nv3dsink sync=false
fi

