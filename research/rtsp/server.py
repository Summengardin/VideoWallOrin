# server.py
import cv2
import gi
import sys
import logging
from threading import Thread
import time
import socket

# Initialize GStreamer and RTSP Server
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GLib

class RTSPServer:
    def __init__(self, rtsp_port=8554, video_device=0, width=1920, height=1080):
        # Initialize GStreamer
        Gst.init(None)
        
        self.width = width
        self.height = height
        self.port = rtsp_port
        self.video_device = video_device
        self.running = False
        
        # Get local IP address
        self.ip_address = self.get_local_ip()
        
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger('RTSPServer')
        
        # Initialize pipeline elements
        self.create_pipeline()

    def get_local_ip(self):
        """Get the local IP address of the machine"""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't need to be reachable
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def create_pipeline(self):
        # Create GStreamer pipeline for RTSP streaming with NVIDIA acceleration
        pipeline_str = (
            # f'v4l2src device=/dev/video{self.video_device} ! '
            'videotestsrc ! '
            f'video/x-raw, width={self.width}, height={self.height} ! '
            'nvvidconv ! '
            'video/x-raw(memory:NVMM) ! '
            'nvv4l2h264enc maxperf-enable=1 preset-level=1 control-rate=1 bitrate=4000000 ! '
            'h264parse ! '
            'rtph264pay name=pay0 pt=96'
        )

        self.logger.info(f"Creating pipeline: {pipeline_str}")

        # Create and configure RTSP server
        self.rtsp_server = GstRtspServer.RTSPServer()
        self.rtsp_server.set_service(str(self.port))
        
        # Create a media factory
        self.factory = GstRtspServer.RTSPMediaFactory()
        self.factory.set_launch(pipeline_str)
        self.factory.set_shared(True)
        
        # Attach factory to server
        self.rtsp_server.get_mount_points().add_factory("/stream", self.factory)

    def start(self):
        """Start the RTSP server"""
        self.running = True
        
        # Start RTSP server
        self.server_id = self.rtsp_server.attach(None)
        if self.server_id == 0:
            self.logger.error("Failed to start RTSP server")
            return False
        
        self.logger.info(f"RTSP server started at rtsp://{self.ip_address}:{self.port}/stream")
        
        # Start GLib main loop in a separate thread
        self.loop = GLib.MainLoop()
        self.loop_thread = Thread(target=self.loop.run)
        self.loop_thread.start()
        
        return True

    def stop(self):
        """Stop the RTSP server"""
        if self.running:
            self.running = False
            self.loop.quit()
            self.loop_thread.join()
            self.logger.info("RTSP server stopped")

def main():
    # Create and start RTSP server
    server = RTSPServer(rtsp_port=8554)
    if not server.start():
        return
    
    try:
        # Main loop
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        server.stop()
        logging.info("Application stopped by user")

if __name__ == "__main__":
    main()