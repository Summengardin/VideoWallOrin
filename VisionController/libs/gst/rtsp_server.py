import socket
import threading
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GstRtspServer, GLib

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not Gst.is_initialized():
    Gst.init(None)


def get_ips():
    local_hostname = socket.gethostname()
    ip_addresses = socket.gethostbyname_ex(local_hostname)[2]
    return ip_addresses


class RTSPServer:
    def __init__(self):
        self.server = GstRtspServer.RTSPServer.new()
        self.server.set_service("8554")  # Default RTSP port

        self.factory = GstRtspServer.RTSPMediaFactory()
        self.factory.set_shared(True)
        self.factory.set_launch(self._launch_string())
        self.server.get_mount_points().add_factory("/stream", self.factory)


        # self.context = GLib.MainContext.new()
        self.loop = GLib.MainLoop()  # Create a GLib MainLoop
        self.running = False
        self.thread = threading.Thread(target=self._run_loop)

        self.server.attach(None)  # Attach server to default context
        

    def _launch_string(self):
        return "shmsrc socket-path=/tmp/vw-rtsp-pipe ! video/x-raw,framerate=200/1,format=NV12,width=3840,height=2160 ! nvvidconv ! video/x-raw(memory:NVMM),format=NV12,width=1280,height=720 ! nvv4l2h264enc enable-full-frame=true ! rtph264pay pt=96 clock-rate=90000 name=pay0"

    def _run_loop(self):
        self.running = True
        logger.info("Starting GLib MainLoop in a separate thread")
        logger.info("RTSP Stream available at:")
        for ip in get_ips():
            logger.info(f"|--->  rtsp://{ip}:8554/stream")
        self.loop.run()

    def start(self):
        if not self.running:
            self.thread.start()

    def stop(self):
        if self.running:
            logger.info("Stopping GLib MainLoop")
            self.loop.quit()
            self.thread.join()
            self.running = False


if __name__ == "__main__":
    import time
    server = RTSPServer()
    try:
        server.start()
        while True:
            time.sleep(1)
            pass  # Keep the main thread alive
    except KeyboardInterrupt:
        logger.info("Stopping RTSP Server")
        server.stop()
