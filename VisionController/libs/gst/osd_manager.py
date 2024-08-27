import time
import threading
from typing import Tuple

from VisionController.libs.utils import build_triangle

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
        self.tiles = [{"texts": [], "triangles": []}, {"texts": [], "triangles": []}, {"texts": [], "triangles": []}, {"texts": [], "triangles": []}]
        self.osd_text_dicts = [{}, {}, {}]
        self.window_size = (1920, 1080)
        self._running = False
        
        self.osd_text_dicts[0] = {
            "text": "UPPER LEFT",
            "x": 0,
            "y": 0,
            "font_size": 18,
            "font_color": (1.0, 1.0, 1.0, 1.0),
            "bg_color": (0.0, 0.0, 0.0, 0.6)
        }

        self.osd_text_dicts[1] = {
            "text": "UPPER MID",
            "x": self.window_size[0] // 2,
            "y": 0,
            "font_size": 18,
            "font_color": (1.0, 1.0, 1.0, 1.0),
            "bg_color": (0.0, 0.0, 0.0, 0.6)
        }

        self.osd_text_dicts[2] = {
            "text": "UPPER RIGHT",
            "x": self.window_size[0] - 200,
            "y": 0,
            "font_size": 18,
            "font_color": (1.0, 1.0, 1.0, 1.0),
            "bg_color": (0.0, 0.0, 0.0, 0.6)
        }

        for tile in self.tiles:
            for i in range(len(self.osd_text_dicts)):
                tile["texts"].append(self.osd_text_dicts[i].copy())

        self.add_triangle(0, 960, 540, 100, 10, (1.0, 0.0, 0.0, 1.0), 0)

        self.start()

    def add_text(self, tile_index: int, text: str, x: int, y: int, font_size: int, color: Tuple[float, float, float, float], bg_color: Tuple[float, float, float, float]) -> None:
        """
        Insert a text message into a tile at a given spot.

        :param int tile_index: The index of the tile to update or insert into.
        :param str text: The text message to insert or update.
        :param int x: The x-coordinate of the text.
        :param int y: The y-coordinate of the text.
        :param int font_size: The size of the font.
        :param Tuple[float, float, float, float] color: The RGBA color of the text.
        :param Tuple[float, float, float, float] bg_color: The RGBA color of the background.
        :return: None
        """
        self.tiles[tile_index]["texts"].append(
            {
                "text": text,
                "x": x,
                "y": y,
                "font_size": font_size,
                "font_color": color,
                "bg_color": bg_color,
            }
        )

    def add_timeout_text(
            self,
            tile_index: int,
            text: str,
            x: int,
            y: int,
            font_size: int,
            color: Tuple[float, float, float, float],
            bg_color: Tuple[float, float, float, float],
            timeout: float = 5,
            spot = None
    ) -> None:
        """
        Update or insert a text message into a tile at a given spot with a
        timeout. If the spot is already occupied, the text message will be
        replaced and the timeout will be reset.

        :param int tile_index: The index of the tile to update or insert into.
        :param str text: The text message to insert or update.
        :param int x: The x-coordinate of the text.
        :param int y: The y-coordinate of the text.
        :param int font_size: The size of the font.
        :param Tuple[float, float, float, float] color: The color of the text.
        :param Tuple[float, float, float, float] bg_color: The background color of the text.
        :param float timeout: (optional) The duration in seconds before the
            message is cleared. Default is 5 seconds.
        """
        now = time.time()
        new_text = {
                "text": text,
                "x": x,
                "y": y,
                "font_size": font_size,
                "font_color": color,
                "bg_color": bg_color,
                "timeout": now + timeout,
            }

        if spot is not None and spot < len(self.tiles[tile_index]["texts"]):
            self.tiles[tile_index]["texts"][spot] = new_text
        else:
            self.tiles[tile_index]["texts"].append(new_text)

    def upsert_timeout_text(
            self,
            tile_index: int,
            text: str,
            spot: int = -1,
            x: int = 960,
            y: int = 980,
            font_size: int = 36,
            color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
            bg_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.6),
            timeout: float = 5):
        """
        Update or insert a text message into a tile at a given spot with a
        timeout. If the spot is already occupied, the text message will be
        replaced and the timeout will be reset.

        :param int tile_index: The index of the tile to update or insert into.
        :param int spot: The index of the spot to update or insert into.
        :param str text: The text message to insert or update.
        :param int x: The x-coordinate of the text.
        :param int y: The y-coordinate of the text.
        :param int font_size: The size of the font.
        :param Tuple[float, float, float, float] color: The color of the text.
        :param Tuple[float, float, float, float] bg_color: The background color of the text.
        :param float timeout: (optional) The duration in seconds before the
            message is cleared. Default is 5 seconds.
        """
        if len(self.tiles[tile_index]["texts"]) > spot:
            self.tiles[tile_index]["texts"][spot]["text"] = text
            self.tiles[tile_index]["texts"][spot]["timeout"] = time.time() + timeout
        else:
            self.add_timeout_text(tile_index, text, x, y, font_size, color, bg_color, timeout, spot)



    def set_text(self, tile: int, spot: int, text: str) -> None:
        self.tiles[tile]["texts"][spot]["text"] = text


    def get_text_dicts(self):
        return self.osd_text_dicts
    
    def get_tile(self, index):
        return self.tiles[index]

    def _update_texts(self):
        now = time.time()
        for tile in self.tiles:
            if tile:
                tile["texts"][:] = [x for x in tile["texts"] if "timeout" not in x or x["timeout"] > now]

    def _update(self):
        cnt = 0
        while self._running:
            self._update_texts()
            
            self.set_text(0, 0, f"UPPER LEFT {cnt}")
            cnt += 1
            time.sleep(0.5)

    def _create_triangle(self, x: int, y: int, radius: int, line_width: int, line_color: tuple, angle: float = 0):
        tri_dict = {
            "vertices": build_triangle((x, y), radius, angle),
            "line_width": line_width,
            "line_color": line_color,
            "angle": angle,
            "radius": radius
        }

        return tri_dict
    

    def add_triangle(self, tile_index: int, x: int, y: int, radius: int, line_width: int, line_color: tuple, angle: float = 0):
        self.tiles[tile_index]["triangles"].append(self._create_triangle(x, y, radius, line_width, line_color, angle))

    def update_triangle_position(self, tile_index: int, triangle_index: int, x: int, y: int, angle: float = 0):
        cur_radius = self.tiles[tile_index]["triangles"][triangle_index]["radius"]
        cur_line_width = self.tiles[tile_index]["triangles"][triangle_index]["line_width"]
        cur_line_color = self.tiles[tile_index]["triangles"][triangle_index]["line_color"]

        self.tiles[tile_index]["triangles"][triangle_index] = self._create_triangle(x, y, cur_radius, cur_line_width, cur_line_color, angle)

    def start(self):
        """Start the update thread."""
        self._running = True
        
        self.update_thread = threading.Thread(target=self._update)
        self.update_thread.start()

    def stop(self):
        """Stop the update thread."""
        self._running = False
        self.update_thread.join(timeout=1)  # Ensure the thread has finished execution

    def __del__(self):
        self.stop()
