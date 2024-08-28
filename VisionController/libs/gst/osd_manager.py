from VisionController.libs.utils import build_triangle
import time
import threading
from typing import Tuple, List, Dict, Any, Optional

import logging
logger = logging.getLogger(__name__)


example_text_dict = {
    "text": "",
    "x": 0,
    "y": 0,
    "font_size": 18,
    "font_color": (1.0, 1.0, 1.0, 1.0),
    "bg_color": (0.0, 0.0, 0.0, 0.6),
    "timeout": 0.0,
}


# class OSDManager:
#     def __init__(self):
#         self.osd_text = ""
#         self.osd_frame_number = 0
#         self.tiles = [{"texts": [], "triangles": []}, {"texts": [], "triangles": []}, {"texts": [], "triangles": []}, {"texts": [], "triangles": []}]
#         self.osd_text_dicts = [{}, {}, {}]
#         self.window_size = (1920, 1080)
#         self._running = False

#         self.osd_text_dicts[0] = {
#             "text": "UPPER LEFT",
#             "x": 0,
#             "y": 0,
#             "font_size": 18,
#             "font_color": (1.0, 1.0, 1.0, 1.0),
#             "font_name": "Noto Serif Bold",
#             "bg_color": (0.0, 0.0, 0.0, 0.6)
#         }

#         self.osd_text_dicts[1] = {
#             "text": "UPPER MID",
#             "x": self.window_size[0] // 2,
#             "y": 0,
#             "font_size": 18,
#             "font_color": (1.0, 1.0, 1.0, 1.0),
#             "font_name": "Noto Serif Bold",
#             "bg_color": (0.0, 0.0, 0.0, 0.6)
#         }

#         self.osd_text_dicts[2] = {
#             "text": "UPPER RIGHT",
#             "x": self.window_size[0] - 200,
#             "y": 0,
#             "font_size": 18,
#             "font_color": (1.0, 1.0, 1.0, 1.0),
#             "font_name": "Noto Serif Bold",
#             "bg_color": (0.0, 0.0, 0.0, 0.6)
#         }

#         for tile in self.tiles:
#             for i in range(len(self.osd_text_dicts)):
#                 tile["texts"].append(self.osd_text_dicts[i].copy())

#         self.add_triangle(0, 960, 540, 100, 10, (1.0, 0.0, 0.0, 1.0), 0)

#         self.start()

#     def add_text(self, tile_index: int, text: str, x: int, y: int, font_size: int, color: Tuple[float, float, float, float], bg_color: Tuple[float, float, float, float]) -> None:
#         """
#         Insert a text message into a tile at a given spot.

#         :param int tile_index: The index of the tile to update or insert into.
#         :param str text: The text message to insert or update.
#         :param int x: The x-coordinate of the text.
#         :param int y: The y-coordinate of the text.
#         :param int font_size: The size of the font.
#         :param Tuple[float, float, float, float] color: The RGBA color of the text.
#         :param Tuple[float, float, float, float] bg_color: The RGBA color of the background.
#         :return: None
#         """
#         self.tiles[tile_index]["texts"].append(
#             {
#                 "text": text,
#                 "x": x,
#                 "y": y,
#                 "font_size": font_size,
#                 "font_color": color,
#                 "bg_color": bg_color,
#                 "font_name": "Noto Serif Bold"
#             }
#         )

#     def add_timeout_text(
#             self,
#             tile_index: int,
#             text: str,
#             x: int,
#             y: int,
#             font_size: int,
#             color: Tuple[float, float, float, float],
#             bg_color: Tuple[float, float, float, float],
#             timeout: float = 5,
#             spot = None
#     ) -> None:
#         """
#         Update or insert a text message into a tile at a given spot with a
#         timeout. If the spot is already occupied, the text message will be
#         replaced and the timeout will be reset.

#         :param int tile_index: The index of the tile to update or insert into.
#         :param str text: The text message to insert or update.
#         :param int x: The x-coordinate of the text.
#         :param int y: The y-coordinate of the text.
#         :param int font_size: The size of the font.
#         :param Tuple[float, float, float, float] color: The color of the text.
#         :param Tuple[float, float, float, float] bg_color: The background color of the text.
#         :param float timeout: (optional) The duration in seconds before the
#             message is cleared. Default is 5 seconds.
#         """
#         now = time.time()
#         new_text = {
#                 "text": text,
#                 "x": x,
#                 "y": y,
#                 "font_size": font_size,
#                 "font_color": color,
#                 "bg_color": bg_color,
#                 "font_name": "Noto Serif Bold",
#                 "timeout": now + timeout,
#             }

#         if spot is not None and spot < len(self.tiles[tile_index]["texts"]):
#             self.tiles[tile_index]["texts"][spot] = new_text
#         else:
#             self.tiles[tile_index]["texts"].append(new_text)

#     def upsert_timeout_text(
#             self,
#             tile_index: int,
#             text: str,
#             spot: int = -1,
#             x: int = 960,
#             y: int = 980,
#             font_size: int = 36,
#             color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
#             bg_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.6),
#             timeout: float = 5):
#         """
#         Update or insert a text message into a tile at a given spot with a
#         timeout. If the spot is already occupied, the text message will be
#         replaced and the timeout will be reset.

#         :param int tile_index: The index of the tile to update or insert into.
#         :param int spot: The index of the spot to update or insert into.
#         :param str text: The text message to insert or update.
#         :param int x: The x-coordinate of the text.
#         :param int y: The y-coordinate of the text.
#         :param int font_size: The size of the font.
#         :param Tuple[float, float, float, float] color: The color of the text.
#         :param Tuple[float, float, float, float] bg_color: The background color of the text.
#         :param float timeout: (optional) The duration in seconds before the
#             message is cleared. Default is 5 seconds.
#         """
#         if len(self.tiles[tile_index]["texts"]) > spot:
#             self.tiles[tile_index]["texts"][spot]["text"] = text
#             self.tiles[tile_index]["texts"][spot]["timeout"] = time.time() + timeout
#         else:
#             self.add_timeout_text(tile_index, text, x, y, font_size, color, bg_color, timeout, spot)


#     def set_text(self, tile: int, spot: int, text: str) -> None:
#         self.tiles[tile]["texts"][spot]["text"] = text


#     def get_text_dicts(self):
#         return self.osd_text_dicts

#     def get_tile(self, index):
#         return self.tiles[index]

#     def _update_texts(self):
#         now = time.time()
#         for tile in self.tiles:
#             if tile:
#                 tile["texts"][:] = [x for x in tile["texts"] if "timeout" not in x or x["timeout"] > now]

#     def _update(self):
#         cnt = 0
#         while self._running:
#             self._update_texts()

#             self.set_text(0, 0, f"UPPER LEFT {cnt}")
#             cnt += 1
#             time.sleep(0.5)

#     def _create_triangle(self, x: int, y: int, radius: int, line_width: int, line_color: tuple, angle: float = 0):
#         tri_dict = {
#             "vertices": build_triangle((x, y), radius, angle),
#             "line_width": line_width,
#             "line_color": line_color,
#             "angle": angle,
#             "radius": radius
#         }

#         return tri_dict


#     def add_triangle(self, tile_index: int, x: int, y: int, radius: int, line_width: int, line_color: tuple, angle: float = 0):
#         self.tiles[tile_index]["triangles"].append(self._create_triangle(x, y, radius, line_width, line_color, angle))

#     def update_triangle_position(self, tile_index: int, triangle_index: int, x: int, y: int, angle: float = 0):
#         cur_radius = self.tiles[tile_index]["triangles"][triangle_index]["radius"]
#         cur_line_width = self.tiles[tile_index]["triangles"][triangle_index]["line_width"]
#         cur_line_color = self.tiles[tile_index]["triangles"][triangle_index]["line_color"]

#         self.tiles[tile_index]["triangles"][triangle_index] = self._create_triangle(x, y, cur_radius, cur_line_width, cur_line_color, angle)

#     def start(self):
#         """Start the update thread."""
#         self._running = True

#         self.update_thread = threading.Thread(target=self._update)
#         self.update_thread.start()

#     def stop(self):
#         """Stop the update thread."""
#         self._running = False
#         self.update_thread.join(timeout=1)  # Ensure the thread has finished execution

#     def __del__(self):
#         self.stop()


class Line:
    def __init__(self, x1: int, y1: int, x2: int, y2: int, width: int, color: Tuple[float, float, float, float]):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.width = width
        self.color = color

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "width": self.width,
            "color": self.color
        }

    def to_dict_ints(self) -> Dict[str, Any]:
        return {
            "x1": int(self.x1),
            "y1": int(self.y1),
            "x2": int(self.x2),
            "y2": int(self.y2),
            "line_width": int(self.width),
            "line_color": self.color
        }


class Triangle:
    def __init__(self, x: int, y: int, radius: int, line_width: int, line_color: tuple, angle: float = 0):
        self.x = x
        self.y = y
        self.radius = radius
        self.line_width = line_width
        self.line_color = line_color
        self.angle = angle

        self.vertices = None
        self.update()

    def update(self):
        logger.debug(f"Updating triangle at ({self.x}, {self.y}) with radius {self.radius} and angle {self.angle}")
        self.vertices = build_triangle(
            (self.x, self.y), self.radius, self.angle)

    def to_lines(self) -> List[Line]:
        lines = []
        num_vertices = len(self.vertices)
        for i in range(num_vertices):
            x1, y1 = self.vertices[i]
            x2, y2 = self.vertices[(i + 1) % num_vertices]
            lines.append(
                Line(x1, y1, x2, y2, self.line_width, self.line_color))
        return lines


class Polygon:
    def __init__(self, vertices: List[Tuple[int, int]], width: int, color: Tuple[float, float, float, float]):
        self.vertices = vertices
        self.width = width
        self.color = color

    def to_lines(self) -> List[Line]:
        lines = []
        num_vertices = len(self.vertices)
        for i in range(num_vertices):
            x1, y1 = self.vertices[i]
            x2, y2 = self.vertices[(i + 1) % num_vertices]
            lines.append(Line(x1, y1, x2, y2, self.width, self.color))
        return lines


# ==============================================================================
# -- OSDManager ---------------------------------------------------------------
# ==============================================================================

class OSDManager:
    def __init__(self, window_size: Tuple[int, int] = (1920, 1080)):
        self.window_size = window_size
        self.elements = {}  # A dictionary to store all elements by ID
        self._running = False
        self._id_counter = 0  # Universal ID counter
        self.start()

        self.default_text_color = (1.0, 1.0, 1.0, 1.0)
        self.default_line_color = (1.0, 0.0, 0.0, 1.0)
        self.default_bg_color = (0.0, 0.0, 0.0, 0.6)
        self.default_font_size = 18
        self.default_font_name = "Noto Serif Bold"

    def _generate_id(self) -> str:
        """Generate a unique ID."""
        element_id = self._id_counter
        self._id_counter += 1
        return str(element_id)

    def start(self):
        """Start the update thread."""
        self._running = True
        self.update_thread = threading.Thread(target=self._update)
        self.update_thread.start()

    def stop(self):
        """Stop the update thread."""
        self._running = False
        # Ensure the thread has finished execution
        self.update_thread.join(timeout=1)

    def _update(self):
        while self._running:
            now = time.time()
            self._cleanup_expired_elements(now)
            time.sleep(0.5)

    def __del__(self):
        self.stop()

    # Public Methods for Managing Shapes and Text with Timeout
    def add_triangle(self, x: int, y: int, radius: int, line_width: int, line_color: Tuple[float, float, float, float], angle: float = 0, timeout: Optional[float] = None, triangle_id: Optional[str] = None) -> int:
        # vertices = build_triangle((x, y), radius, angle)
        if triangle_id is None:
            triangle_id = self._generate_id()
        self.elements[triangle_id] = {
            "type": "triangle",
            "object": Triangle(x, y, radius, line_width, line_color, angle),
            "timeout": time.time() + timeout if timeout else None
        }
        return triangle_id

    def add_polygon(self, vertices: List[Tuple[int, int]], line_width: int, line_color: Tuple[float, float, float, float], timeout: Optional[float] = None, polygon_id: Optional[str] = None) -> int:
        if polygon_id is None:
            polygon_id = self._generate_id()
        self.elements[polygon_id] = {
            "type": "polygon",
            "object": Polygon(vertices, line_width, line_color),
            "timeout": time.time() + timeout if timeout else None
        }
        return polygon_id

    def add_text(self, text: str, x: int, y: int, font_size: int, color: Tuple[float, float, float, float], bg_color: Tuple[float, float, float, float], timeout: Optional[float] = None, text_id: Optional[str] = None) -> int:
        if text_id is None:
            text_id = self._generate_id()
        self.elements[text_id] = {
            "type": "text",
            "object": {
                "text": text,
                "x": x,
                "y": y,
                "font_size": font_size,
                "font_color": color,
                "bg_color": bg_color,
                "font_name": "Noto Serif Bold"
            },
            "timeout": time.time() + timeout if timeout else None
        }
        return text_id

    def update_triangle(self, element_id: str, x: int, y: int, radius: int, line_width: int, line_color: Tuple[float, float, float, float], angle: float = 0):
        if element_id in self.elements and self.elements[element_id]["type"] == "triangle":
            vertices = build_triangle((x, y), radius, angle)
            self.elements[element_id]["object"] = Triangle(
                vertices, line_width, line_color)

    def update_polygon(self, element_id: str, vertices: List[Tuple[int, int]], line_width: int, line_color: Tuple[float, float, float, float]):
        if element_id in self.elements and self.elements[element_id]["type"] == "polygon":
            self.elements[element_id]["object"] = Polygon(
                vertices, line_width, line_color)

    def update_text(self, text_id: str, text: str):
        if text_id in self.elements and self.elements[text_id]["type"] == "text":
            self.elements[text_id]["object"]["text"] = text

    def upsert_triangle(self,
                        triangle_id: Optional[str] = None,
                        x: Optional[int] = None,
                        y: Optional[int] = None,
                        radius: Optional[int] = None,
                        line_width: Optional[int] = None,
                        line_color: Optional[Tuple[float,
                                                   float, float, float]] = None,
                        angle: Optional[float] = None,
                        timeout: Optional[float] = None) -> str:
        """ Update or create a triangle with the given parameters. """
        logger.debug(f"upsert_triangle: {triangle_id}, {x}, {y}, {radius}, {line_width}, {line_color}, {angle}, {timeout}")
        if triangle_id is not None and triangle_id in self.elements and self.elements[triangle_id]["type"] == "triangle":
            if x is not None:
                self.elements[triangle_id]["object"].x = x
            if y is not None:
                self.elements[triangle_id]["object"].y = y
            if radius is not None:
                self.elements[triangle_id]["object"].radius = radius
            if line_width is not None:
                self.elements[triangle_id]["object"].line_width = line_width
            if line_color is not None:
                self.elements[triangle_id]["object"].line_color = line_color
            if angle is not None:
                self.elements[triangle_id]["object"].angle = angle
            if timeout is not None:
                self.elements[triangle_id]["timeout"] = time.time() + timeout

            self.elements[triangle_id]["object"].update()

            return triangle_id

        return self.add_triangle(x, y, radius, line_width, line_color, angle, timeout, triangle_id)

    def upsert_text(self,
                    text: str,
                    text_id: Optional[str] = None,
                    x: Optional[int] = None,
                    y: Optional[int] = None,
                    font_size: Optional[int] = None,
                    color: Optional[Tuple[float, float, float, float]] = None,
                    bg_color: Optional[Tuple[float,
                                             float, float, float]] = None,
                    timeout: Optional[float] = None) -> str:
        """ Add or update a text element with the given parameters. """

        logger.debug(
            f"upsert_text: {text}, {text_id}, {x}, {y}, {font_size}, {color}, {bg_color}, {timeout}")

        if text_id is not None and text_id in self.elements and self.elements[text_id]["type"] == "text":
            if text is not None:
                self.elements[text_id]["object"]["text"] = text
            if x is not None:
                self.elements[text_id]["object"]["x"] = x
            if y is not None:
                self.elements[text_id]["object"]["y"] = y
            if font_size is not None:
                self.elements[text_id]["object"]["font_size"] = font_size
            if color is not None:
                self.elements[text_id]["object"]["font_color"] = color
            if bg_color is not None:
                self.elements[text_id]["object"]["bg_color"] = bg_color
            if timeout is not None:
                self.elements[text_id]["timeout"] = time.time() + timeout

            return text_id

        return self.add_text(text, x, y, font_size, color, bg_color, timeout, text_id)

    def remove_element(self, element_id: str):
        if element_id in self.elements:
            del self.elements[element_id]

    def _cleanup_expired_elements(self, current_time: float):
        self.elements = {element_id: element for element_id, element in self.elements.items(
        ) if element["timeout"] is None or element["timeout"] > current_time}

    def get_all_lines_as_dicts(self) -> List[Dict]:
        lines = []
        for element in self.elements.values():
            if element["type"] == "triangle" or element["type"] == "polygon":
                lines.extend(element["object"].to_lines())
        return [line.to_dict_ints() for line in lines]

    def get_all_texts(self) -> List[Dict]:
        return [element["object"] for element in self.elements.values() if element["type"] == "text"]
