import pyds

class OSDManager:
    def __init__(self, pipeline_manager):
        self.pipeline_manager = pipeline_manager
        self.osd_text = ""
        self.osd_frame_number = 0
        self.osd_text_dict = []

    def setup_osd_text(self):
        pass

    def add_timeout_text(self):
        pass

    def draw_graphics(self):
        pass

    def _osd_sink_pad_buffer_probe(self, pad, info, user_data):
        pass
