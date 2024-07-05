import gi
import signal
# gi.require_version('Aravis', '0.8')
from gi.repository import Aravis, GLib


class CameraAcquisition:
    def __init__(self):
        self.camera = None
        self.stream = None
        self.main_loop = None
        self.buffer_count = 0
        self.cancel = False

    def set_cancel(self, signum, frame):
        self.cancel = True

    def new_buffer_cb(self, stream):
        buffer = stream.try_pop_buffer()
        if buffer:
            if buffer.get_status() == Aravis.BufferStatus.SUCCESS:
                self.buffer_count += 1
            # Image processing can be done here
            stream.push_buffer(buffer)

    def periodic_task_cb(self):
        print(f"Frame rate = {self.buffer_count} Hz")
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
        self.camera = Aravis.Camera.new(None)

        if self.camera:
            self.camera.set_region(0, 0, 200, 200)
            self.camera.set_frame_rate(10.0)
            payload = self.camera.get_payload()

            self.stream = self.camera.create_stream(None, None)

            if self.stream:
                for _ in range(50):
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

if __name__ == "__main__":
    acquisition = CameraAcquisition()
    acquisition.start_acquisition()
