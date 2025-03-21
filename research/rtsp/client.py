import cv2
import logging
import argparse

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
                'nvv4l2decoder ! '  # Use NVIDIA decoder
                'nvvidconv ! '      # Convert for display
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
                'avdec_h264 ! '    # Use CPU decoder
                'videoconvert ! '
                'video/x-raw, format=BGR ! '
                'appsink sync=false'
            )

        self.logger.info(f"Connecting to: rtsp://{self.server_ip}:{self.port}/stream")
        self.cap = cv2.VideoCapture(gst_str, cv2.CAP_GSTREAMER)
        
        if not self.cap.isOpened():
            raise RuntimeError("Failed to open RTSP stream")

    def run(self):
        """Start receiving and displaying the video stream"""
        self.logger.info("Starting video display")
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    self.logger.error("Failed to receive frame")
                    break

                cv2.imshow('RTSP Stream', frame)
                
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