import cv2
import logging
import argparse
import datetime

class RTSPClient:
    def __init__(self, server_ip, port=8554, use_gpu=True):
        self.server_ip = server_ip
        self.port = port
        self.use_gpu = use_gpu
        
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger('RTSPClient')
        
        # Initialize video capture
        self.init_capture()

    def init_capture(self):
        # Create GStreamer pipeline for receiving
        if self.use_gpu:
            gst_str = (
                f'rtspsrc location=rtsp://{self.server_ip}:{self.port}/stream latency=0 ! '
                'rtph264depay ! '
                'h264parse ! '
                'nvv4l2decoder ! '
                'nvvidconv ! '
                'video/x-raw, format=BGRx ! '
                'videoconvert ! '
                'video/x-raw, format=BGR ! '
                'appsink sync=false'
            )
        else:
            gst_str = (
                f'rtspsrc location=rtsp://{self.server_ip}:{self.port}/stream latency=0 ! '
                'rtph264depay ! '
                'h264parse ! '
                'avdec_h264 ! '
                'videoconvert ! '
                'video/x-raw, format=BGR ! '
                'appsink sync=false'
            )

        self.logger.info(f"Connecting to: rtsp://{self.server_ip}:{self.port}/stream")
        self.cap = cv2.VideoCapture(gst_str, cv2.CAP_GSTREAMER)
        
        if not self.cap.isOpened():
            raise RuntimeError("Failed to open RTSP stream")

    def add_timestamp(self, frame):
        """Add client timestamp overlay to the frame"""
        timestamp = datetime.datetime.now().strftime('%H:%M:%S.%f')
        
        # Create semi-transparent background for text
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 80), (300, 140), (0, 0, 0), -1)
        alpha = 0.7
        frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
        
        # Add timestamp
        cv2.putText(frame, 
                   f"Client Time: {timestamp}", 
                   (20, 110),
                   cv2.FONT_HERSHEY_SIMPLEX, 
                   0.7,
                   (255, 0, 0),  # Blue color for client
                   2)
        
        return frame

    def run(self):
        """Start receiving and displaying the video stream"""
        self.logger.info("Starting video display")
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    self.logger.error("Failed to receive frame")
                    break

                # Add client timestamp
                frame_with_timestamp = self.add_timestamp(frame)
                
                cv2.imshow('Client View', frame_with_timestamp)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        finally:
            self.cap.release()
            cv2.destroyAllWindows()
            self.logger.info("Client stopped")

def main():
    parser = argparse.ArgumentParser(description='RTSP Client')
    parser.add_argument('server_ip', help='IP address of the RTSP server')
    parser.add_argument('--port', type=int, default=8554, help='RTSP server port')
    parser.add_argument('--no-gpu', action='store_true', help='Disable GPU acceleration')
    
    args = parser.parse_args()
    
    client = RTSPClient(args.server_ip, args.port, use_gpu=not args.no_gpu)
    client.run()

if __name__ == "__main__":
    main()