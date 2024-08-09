import time
from visca_over_ip import Camera

cam = Camera('10.1.3.78', 1569)  # Your camera's IP address or hostname here

while True:
    cam.zoom_to(0)
    zoom = cam.get_zoom_position()
    print(zoom)

    time.sleep(1)  # wait one second

    cam.zoom_to(1)
    zoom = cam.get_zoom_position()
    print(zoom)

    time.sleep(1)  # wait one second
