import multiprocessing
import multiprocessing.process
from multiprocessing import shared_memory

from frame_grabber import FrameGrabber
from gstreamer_pipeline import GStreamerPipeline
import numpy as np

if __name__ == "__main__":
    frame_shape = (1080, 1920)
    shm_name = 'frame_shm'
    shm = shared_memory.SharedMemory(name=shm_name, create=True, size=np.prod(frame_shape))
    

    camera_name = '10.1.3.75'

    try:

        frame_grabber = FrameGrabber(camera_name, shm_name=shm_name, frame_width=frame_shape[1], frame_height=frame_shape[0])
        grabber_process = multiprocessing.Process(target=frame_grabber.start)
        grabber_process.start()

    # Start GStreamer pipeline
        gstreamer_pipeline = GStreamerPipeline(frame_width=frame_shape[1], frame_height=frame_shape[0], shm_name=shm_name)
        gstreamer_pipeline.start_pipeline()

    # Keep the main thread running
        try:
            while True:
                pass
        except KeyboardInterrupt:
            grabber_process.terminate()
            grabber_process.join()
    

    finally:
        shm.close()
        shm.unlink()

