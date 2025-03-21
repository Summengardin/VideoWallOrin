import cv2
import gi
import sys
import logging
from threading import Thread
import time
import socket
import datetime
import numpy as np

# Initialize GStreamer and RTSP Server
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GLib

try:
    import ctypes
    x11 = ctypes.cdll.LoadLibrary('libX11.so.6')
    x11.XInitThreads()
except Exception as e:
    print(f"Warning: Failed to initialize X11 threads: {e}")

class FrameGenerator:
    def __init__(self, width=1920, height=1080):
        self.width = width
        self.height = height
        self.frame_count = 0
        
    def create_test_pattern(self):
        """Create a test pattern with moving elements"""
        # Create base frame
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Add static elements
        # Color bars
        bar_width = self.width // 7
        colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (0, 255, 255),  # Cyan
            (255, 0, 255),  # Magenta
            (255, 255, 255) # White
        ]
        
        for i, color in enumerate(colors):
            x1 = i * bar_width
            x2 = (i + 1) * bar_width
            cv2.rectangle(frame, (x1, 0), (x2, self.height), color, -1)
            
        # Add moving circle
        circle_radius = 50
        circle_x = int((self.frame_count % 100) * (self.width - 2*circle_radius) / 100) + circle_radius
        circle_y = self.height // 2
        cv2.circle(frame, (circle_x, circle_y), circle_radius, (0, 0, 0), -1)
        
        # Add frame counter
        cv2.putText(frame, 
                   f"Frame: {self.frame_count}", 
                   (20, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 
                   1,
                   (0, 0, 0),
                   2)
        
        self.frame_count += 1
        return frame

class RTSPServer:
    def __init__(self, rtsp_port=8554, width=1920, height=1080):
        # Initialize GStreamer
        Gst.init(None)
        
        self.width = width
        self.height = height
        self.port = rtsp_port
        self.running = False
        
        # Get local IP address
        self.ip_address = self.get_local_ip()
        
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger('RTSPServer')
        
        # Initialize frame generator
        self.frame_generator = FrameGenerator(width, height)
        
        # Initialize pipeline elements
        self.create_pipeline()
        
        # Frame rate control
        self.target_fps = 30
        self.frame_interval = 1.0 / self.target_fps

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def add_timestamp(self, frame):
        """Add timestamp overlay to the frame"""
        timestamp = datetime.datetime.now().strftime('%H:%M:%S.%f')
        
        # Create semi-transparent background for text
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (300, 70), (0, 0, 0), -1)
        alpha = 0.7
        frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
        
        # Add timestamp
        cv2.putText(frame, 
                   f"Server Time: {timestamp}", 
                   (20, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 
                   0.7,
                   (0, 255, 0),
                   2)
        
        return frame

    def create_pipeline(self):
        """Create GStreamer pipeline for RTSP streaming"""
        pipeline_str = (
            'appsrc name=source is-live=true format=GST_FORMAT_TIME ! '
            'videoconvert ! '
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

    def process_frame(self, input_frame=None):
        """Process input frame or generate test pattern"""
        if input_frame is None:
            # Generate test pattern if no input frame provided
            frame = self.frame_generator.create_test_pattern()
        else:
            # Use provided frame
            frame = input_frame.copy()
        
        # Add timestamp overlay
        frame = self.add_timestamp(frame)
        return frame

    def start(self):
        """Start the RTSP server and local display"""
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
        
        # Start display thread
        self.display_thread = Thread(target=self.display_loop)
        self.display_thread.start()
        
        return True

    def display_loop(self):
        """Main loop for displaying video"""
        last_frame_time = time.time()
        
        while self.running:
            current_time = time.time()
            elapsed = current_time - last_frame_time
            
            if elapsed >= self.frame_interval:
                # Process frame
                frame = self.process_frame()
                # Display the frame
                cv2.imshow('Server View', frame)
                
                print("running")
                # Update last frame time
                last_frame_time = current_time
                
                # Break loop if 'q' is pressed
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.running = False
                    break
                
            else:
                # Sleep for a short time to avoid consuming too much CPU
                time.sleep(max(0, self.frame_interval - elapsed))

    def stop(self):
        """Stop the RTSP server and clean up"""
        if self.running:
            self.running = False
            self.loop.quit()
            self.loop_thread.join()
            self.display_thread.join()
            cv2.destroyAllWindows()
            self.logger.info("RTSP server stopped")

    def feed_frame(self, frame):
        """Feed an external frame to the server"""
        if not self.running:
            return False
        return self.process_frame(frame)

def main():
    # Create and start RTSP server
    server = RTSPServer(rtsp_port=8554, width=1920, height=1080)
    if not server.start():
        return
    


    try:
        # Main loop
        while server.running:
            
            time.sleep(0.01)
            

        
    except KeyboardInterrupt:
        server.stop()
        logging.info("Application stopped by user")

if __name__ == "__main__":
    main()