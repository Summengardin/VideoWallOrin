import time
import threading

example_text_dict = {
    "text": "",
    "x": 0,
    "y": 0,
    "font_size": 18,
    "font_color": (1.0, 1.0, 1.0, 1.0),
    "bg_color": (0.0, 0.0, 0.0, 0.6),
    "timeout": 0.0,
}


class OSDManager:
    def __init__(self):
        self.osd_text = ""
        self.osd_frame_number = 0
        self.tiles = [None, None, None, None]
        self.osd_text_dicts = [{}, {}, {}]
        self.update_thread = threading.Thread(target=self._update_thread, daemon=True)
        self.update_thread.start()
        self.window_size = (1920,1080)

        self._running = True


        self.osd_text_dicts[0] = {
            "text": "LEFT TEXT",
            "x": 0,
            "y": 0,
            "font_size": 18,
            "font_color": (1.0, 1.0, 1.0, 1.0),
            "bg_color": (0.0, 0.0, 0.0, 0.6)
        }

        self.osd_text_dicts[1] = {
            "text": "MIDDLE TEXT",
            "x": self.window_size[0] // 2,
            "y": 0,
            "font_size": 18,
            "font_color": (1.0, 1.0, 1.0, 1.0),
            "bg_color": (0.0, 0.0, 0.0, 0.6)
        }

        self.osd_text_dicts[2] = {
            "text": "RIGHT TEXT",
            "x": self.window_size[0] - 200,
            "y": 0,
            "font_size": 18,
            "font_color": (1.0, 1.0, 1.0, 1.0),
            "bg_color": (0.0, 0.0, 0.0, 0.6)
        }

        for i in range(4):
            self.tiles[i] = self.osd_text_dicts.copy()


    def add_text(self, text, x, y, font_size, color, bg_color):
        self.osd_text_dicts.append(
            {
                "text": text,
                "x": x,
                "y": y,
                "font_size": font_size,
                "font_color": color,
                "bg_color": bg_color,
            }
        )

    def add_timeout_text(self, text, x, y, font_size, color, bg_color, timeout=5):
        now = time.time()
        self.osd_text_dicts.append(
            {
                "text": text,
                "x": x,
                "y": y,
                "font_size": font_size,
                "font_color": color,
                "bg_color": bg_color,
                "timeout": now + timeout,
            }
        )

    def get_text_dicts(self):
        return self.osd_text_dicts
    
    def get_tile(self, index):
        return self.tiles[index]


    def _update_texts(self):
        now = time.time()
        self.osd_text_dicts = [x for x in self.osd_text_dicts if "timeout" not in x or x["timeout"] > now]


    def _update_thread(self):
        while self._running:
            self._update_texts()
            time.sleep(0.5)

    def _osd_sink_pad_buffer_probe(self, pad, info, user_data):
        pass


    def __del__(self):
        print("\n Stopping OSD Manager")
        self._running = False
        self.update_thread.join()