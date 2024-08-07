import threading
import time


from libs.pipeline_manager import PipelineManager
from libs.types import SourceType, Source, Camera


Cameras = [Camera(ip="10.1.3.74", type="Basler", width=1920, height=1080, format="BayerRG8", framerate=50), Camera(ip="10.1.3.79", type="TheImagingSource", width=1920, height=1080, format="BayerRG8", framerate=50)]





if __name__ == "__main__":



    pipeline_manager = PipelineManager()

    seq_step = 0
    add_remove = 1
    def source_sequencer():
        global seq_step, add_remove
        if seq_step >= len(Cameras):
            seq_step = len(Cameras) - 1
            add_remove = -1

        if seq_step < 0:
            seq_step = 0
            add_remove = 1

        index = seq_step
        seq_step += add_remove

        if add_remove == 1:
            pipeline_manager.add_source(index, Cameras[index])
        else:
            pipeline_manager.remove_source(index)
            

    pipeline_thread = threading.Thread(target=pipeline_manager.start)
    pipeline_thread.start()
    

    try:
        while True:
            time.sleep(3)
            source_sequencer()        
    except KeyboardInterrupt:
        pass
    finally:
        pipeline_manager.stop()


    pipeline_thread.join()