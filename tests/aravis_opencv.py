import cv2
import numpy as np
import gi

gi.require_version('Aravis', '0.8')
from gi.repository import Aravis

def main():
    # Initialize Aravis
    Aravis.update_device_list()

    # Create a camera object
    camera = Aravis.Camera.new(None)
    if not camera:
        print("No camera found")
        return

    # Start the acquisition
    camera.start_acquisition()

    try:
        while True:
            # Acquire a frame
            frame = camera.acquire_buffer()
            if frame is None:
                print("Failed to acquire buffer")
                continue

            # Convert the frame to a numpy array
            payload = frame.get_image_data()
            width = frame.get_image_width()
            height = frame.get_image_height()
            image = np.ndarray(buffer=payload, dtype=np.uint8, shape=(height, width, 1))

            # Display the frame using OpenCV
            cv2.imshow('Aravis Camera', image)

            # Break the loop on 'q' key press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            # Release the frame
            camera.release_buffer(frame)

    finally:
        # Stop the acquisition
        camera.stop_acquisition()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
