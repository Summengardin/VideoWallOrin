import gi
import numpy as np
import cv2
import socket
import time

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GLib

Gst.init(None)

def get_ips():
    local_hostname = socket.gethostname()
    ip_addresses = socket.gethostbyname_ex(local_hostname)[2]
    return ip_addresses

class SensorFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, width=1920, height=1080, fps=60, **properties):
        super(SensorFactory, self).__init__(**properties)
        self.number_frames = 0
        self.fps = fps
        self.width = width
        self.height = height
        self.frame = None
        self.launch_string = (
            'appsrc name=source is-live=true block=true format=GST_FORMAT_TIME '
            f'caps=video/x-raw,format=BGRx,width={self.width},height={self.height},framerate={self.fps}/1 '
            # '! videoconvert ! x264enc speed-preset=ultrafast tune=zerolatency '
            '! nvvideoconvert compute-hw=1 ! nvv4l2h265enc ! h265parse '
            '! rtph265pay config-interval=1 name=pay0 pt=96'
        )

        self.dummy_frame = np.zeros((self.height, self.width, 4), dtype=np.uint8)

    def set_frame(self, frame):
        self.frame = frame

    def on_need_data(self, src, length):
        if self.frame is None:
            self.frame = self.dummy_frame
            print("No frame, using dummy frame")
        
        data = self.frame.tobytes()
        buf = Gst.Buffer.new_allocate(None, len(data), None)
        buf.fill(0, data)
        timestamp = self.number_frames * Gst.SECOND // self.fps
        buf.pts = buf.dts = timestamp
        buf.duration = Gst.SECOND // self.fps
        self.number_frames += 1

        retval = src.emit('push-buffer', buf)
        if retval != Gst.FlowReturn.OK:
            print("Error pushing buffer")

    def do_create_element(self, url):
        return Gst.parse_launch(self.launch_string)

    def do_configure(self, rtsp_media):
        appsrc = rtsp_media.get_element().get_child_by_name('source')
        appsrc.connect('need-data', self.on_need_data)

        rtsp_media.connect('unprepared', self.on_client_disconnected)

    def on_client_disconnected(self, rtsp_media):
        print("Client disconnected")
        self.number_frames = 0

class GstServer:
    def __init__(self):
        self.server = GstRtspServer.RTSPServer()
        self.port = "8554"
        self.mount = "test"

        self.factory = SensorFactory()
        self.factory.set_shared(True)
        self.mounts = self.server.get_mount_points()
        self.mounts.add_factory(f"/{self.mount}", self.factory)
        self.server.set_service(str(self.port))
        self.server.attach(None)

        print("Stream is running on: ")
        for ip in get_ips():
            print(f"    rtsp://{ip}:{self.port}/{self.mount}")


running = True
start_time = time.time()
def format_time(seconds):
    milliseconds = int((seconds - int(seconds)) * 10000)  # Four decimal places
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return "%02d:%02d:%02d.%04d" % (hours, minutes, seconds, milliseconds)


if __name__ == "__main__":
    server = GstServer()

    # cap = cv2.VideoCapture(0) 
    try:
        while True:
            # ret, frame = cap.read()
            # frame = np.random.randint(0, 256, (480, 640, 4), dtype=np.uint8) # BGRx
            frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
            ret = True

            if not ret:
                break
            

            elapsed_time = time.time() - start_time
            cv2.putText(frame, format_time(elapsed_time), (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)


            # Pass frame to RTSP stream
            cv2.imshow("RTSP Stream", frame)
            server.factory.set_frame(frame)
            
            # time.sleep (0.001)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break   
    except KeyboardInterrupt:
        pass
    # cap.release()
    cv2.destroyAllWindows()

    print("\n\nGoodbye!")
