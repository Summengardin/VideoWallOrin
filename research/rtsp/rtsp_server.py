import gi
import numpy as np
import cv2

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GLib

Gst.init(None)

class SensorFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, width=640, height=480, fps=30, **properties):
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
            '! nvvideoconvert ! nvv4l2h264enc ! h264parse '
            '! rtph264pay config-interval=1 name=pay0 pt=96'
        )

        self.dummy_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

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
        self.factory = SensorFactory()
        self.factory.set_shared(True)
        self.mounts = self.server.get_mount_points()
        self.mounts.add_factory("/test", self.factory)
        self.server.attach(None)

    def run(self):
        loop = GLib.MainLoop()
        loop.run()


if __name__ == "__main__":
    server = GstServer()
    print("RTSP server is running at rtsp://127.0.0.1:8554/test")

    # cap = cv2.VideoCapture(0)  # Use OpenCV to capture video from a camera
    while True:
        # ret, frame = cap.read()
        frame = np.random.randint(0, 256, (480, 640, 4), dtype=np.uint8)
        ret = True

        if not ret:
            break
        
        # Provide frame to RTSP factory
        server.factory.set_frame(frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # cap.release()
    cv2.destroyAllWindows()
