import argparse
import subprocess
import threading

def launch_camera(cam, dbg):
    # Properties for each camera
    camera_properties = {
        "10.1.3.75": {
            "width": 1920,
            "height": 1080,
            "framerate": "54/1",
            "format": "rggb"
        },
        "10.1.3.74": {
            "width": 1920,
            "height": 1080,
            "framerate": "100/1",
            "format": "rggb"
        },
        "10.1.3.76": {
            "width": 1920,
            "height": 1080,
            "framerate": "100/1",
            "format": "rggb"
        },
        "10.1.3.77": {
            "width": 1920,
            "height": 1080,
            "framerate": "100/1",
            "format": "rggb"
        }
    }

    # Determine camera properties
    if cam in camera_properties:
        props = camera_properties[cam]
        width = props["width"]
        height = props["height"]
        framerate = props["framerate"]
        fmt = props["format"]

        # Construct the gst-launch command
        cmd = [
            "gst-launch-1.0",
            f"aravissrc camera-name={cam}",
            f"! video/x-bayer,width={width},height={height},framerate={framerate},format={fmt}",
            "! tcamconvert",
            "! videoconvert",
            "! nvvideoconvert ! 'video/x-raw(memory:NVMM),format=NV12'",
            "! nv3dsink sync=false"
            #"! xvimagesink sync=false"
        ]

        # Execute the command
        subprocess.run(" ".join(cmd), shell=True)
    else:
        print(f"Camera IP {cam} not recognized.")

def main():
    # Default values
    cam_default = ["10.1.3.75", "10.1.3.74", "10.1.3.76", "10.1.3.77"]
    dbg_default = "0"

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Display camera feed.')
    parser.add_argument('cams', nargs='*', default=cam_default, help='Camera IP addresses')
    parser.add_argument('dbg', nargs='?', default=dbg_default, help='Debug level')
    args = parser.parse_args()

    cams = args.cams
    dbg = args.dbg

    threads = []

    for cam in cams:
        thread = threading.Thread(target=launch_camera, args=(cam, dbg))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()
