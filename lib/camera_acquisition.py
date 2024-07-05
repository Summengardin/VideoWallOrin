import gi
import numpy as np
import signal
import multiprocessing as mp
gi.require_version('Aravis', '0.8')
from gi.repository import Aravis, GLib

BUFFER_SIZE = 1


class CameraAcquisition:
    def __init__(self, frame_queue):
        self.camera = None
        self.stream = None
        self.main_loop = None
        self.buffer_count = 0
        self.cancel = False
        self.frame_queue = frame_queue


    def set_cancel(self, signum, frame):
        self.cancel = True


    def new_buffer_cb(self, stream):
        buffer = stream.try_pop_buffer()
        if buffer and buffer.get_status() == Aravis.BufferStatus.SUCCESS:
            
            self.buffer_count += 1
            
            payload = buffer.get_data()

            width = buffer.get_image_width()
            height = buffer.get_image_height()

            frame = np.frombuffer(payload, dtype=np.uint8).reshape((height, width, 3))
            self.frame_queue.put(frame)

            stream.push_buffer(buffer)


    def periodic_task_cb(self):
        print(f"Frame rate = {self.buffer_count} FPS")
        self.buffer_count = 0

        if self.cancel:
            self.main_loop.quit()
            return False

        return True


    def control_lost_cb(self, gv_device):
        print("Control lost")
        self.cancel = True


    def start_acquisition(self):
        Aravis.update_device_list()
        print()
        print(f"There are {Aravis.get_n_interfaces()} interfaces")
        for i in range(Aravis.get_n_interfaces()):
            print(f"Interface {i}: {Aravis.get_interface_id(i)}")

        print()
        print("Found %d cameras:" % Aravis.get_n_devices())
        print("IP, ID, Model, Serial number, Physical ID, Protocol")
        for i in range (Aravis.get_n_devices()):
            print(f"    - {Aravis.get_device_address(i)}, {Aravis.get_device_id(i)}, {Aravis.get_device_model(i)}, {Aravis.get_device_serial_nbr(i)}, {Aravis.get_device_physical_id(i)}, {Aravis.get_device_protocol(i)}")

        print()

        try:
            self.camera = Aravis.Camera.new("10.1.3.77")
        except TypeError:
            print ("No camera found")
            exit ()

        
    

        if self.camera:
            print(f"===== Connected to Camera: {self.camera.get_vendor_name()} - {self.camera.get_model_name()} - {self.camera.get_device_id()} =====\n")

            print("Available pixel formats:")
            format_int = self.camera.dup_available_pixel_formats()
            format_disp = self.camera.dup_available_pixel_formats_as_display_names()
            format_str = self.camera.dup_available_pixel_formats_as_strings()

            for i in range(len(format_int)):
                print(f"{format_disp[i]}: {format_str[i]}  -  {format_int[i]}")

            print()

            self.camera.set_pixel_format_from_string("RGB8")
            print(f"Using pixel format: {self.camera.get_pixel_format_as_string()}")

            self.camera.set_region(0, 0, 1920, 1080)
            self.camera.set_frame_rate(30.0)
            payload = self.camera.get_payload()

            self.stream = self.camera.create_stream(None, None)

            if self.stream:
                for _ in range(BUFFER_SIZE):
                    self.stream.push_buffer(Aravis.Buffer.new(payload))

                self.camera.start_acquisition()

                self.stream.connect("new-buffer", self.new_buffer_cb)
                self.stream.set_emit_signals(True)

                self.camera.get_device().connect("control-lost", self.control_lost_cb)

                GLib.timeout_add_seconds(1, self.periodic_task_cb)

                self.main_loop = GLib.MainLoop()

                signal.signal(signal.SIGINT, self.set_cancel)

                self.main_loop.run()

                self.camera.stop_acquisition()
                self.stream.set_emit_signals(False)

                self.stream = None
                self.camera = None
            else:
                print("Can't create stream")
        else:
            print("No camera found")

def acquisition_process(frame_queue):
    acquisition = CameraAcquisition(frame_queue)
    acquisition.start_acquisition()

if __name__ == "__main__":
    import cv2 
    import time

    # cv2.namedWindow('Frame', cv2.WINDOW_NORMAL)

    frame_queue = mp.Queue(maxsize=10)
    p = mp.Process(target=acquisition_process, args=(frame_queue,))
    p.start()

    try:
        while True:
            if not frame_queue.empty():
                frame = frame_queue.get()
                # frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # cv2.imshow('Frame', frame)
                # if cv2.waitKey(1) & 0xFF == ord('q'):
                #     break
    except KeyboardInterrupt:
        pass
    finally:
        # p.terminate()
        p.join()
        # cv2.destroyAllWindows()