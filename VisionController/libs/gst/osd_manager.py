from VisionController.libs.utils import build_triangle, check_points_inside_frame, move_vertices_inside_frame
import time
import threading
from typing import Tuple, List, Dict, Any, Optional
import math
from itertools import pairwise


import logging
logger = logging.getLogger(__name__)


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
        logger.debug(
            f"Updating triangle at ({self.x}, {self.y}) with radius {self.radius} and angle {self.angle}")
        self.vertices = build_triangle(
            (self.x, self.y), self.radius, self.angle)
        
        self.vertices = move_vertices_inside_frame(self.vertices, (0, 0, 1920, 1080))

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
        self.elements = {}
        self._running = False
        self._id_counter = 0
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
        self.update_thread.join(timeout=1)

    def _update(self):
        while self._running:
            now = time.time()
            self._cleanup_expired_elements(now)
            time.sleep(0.5)

    def __del__(self):
        self.stop()

    def create_triangle(self, x: int, y: int, radius: int, line_width: int, line_color: Tuple[float, float, float, float], angle: float = 0, timeout: Optional[float] = None, triangle_id: Optional[str] = None) -> int:
        # vertices = build_triangle((x, y), radius, angle)
        if triangle_id is None:
            triangle_id = self._generate_id()
        self.elements[triangle_id] = {
            "type": "triangle",
            "object": Triangle(x, y, radius, line_width, line_color, angle),
            "timeout": time.time() + timeout if timeout > 0 else -1
        }
        return triangle_id

    def create_polygon(self, vertices: List[Tuple[int, int]], line_width: int, line_color: Tuple[float, float, float, float], timeout: Optional[float] = None, polygon_id: Optional[str] = None) -> int:
        if polygon_id is None:
            polygon_id = self._generate_id()
        self.elements[polygon_id] = {
            "type": "polygon",
            "object": Polygon(vertices, line_width, line_color),
            "timeout": time.time() + timeout if timeout > 0 else -1
        }
        return polygon_id

    def create_text(self, text: str = "", 
                            x: int = 0, 
                            y: int = 0, 
                            alignment: str = "left", 
                            font_size: int = None, 
                            color: Tuple[float, float, float, float] = None, 
                            bg_color: Tuple[float, float, float, float] = None, 
                            timeout: Optional[float] = None, 
                            text_id: Optional[str] = None) -> int:
        if text_id is None:
            text_id = self._generate_id()
        try:
            text = f"{float(text):.2f}"
        except ValueError:
            pass
        self.elements[text_id] = {
            "type": "text",
            "object": {
                "text": text,
                "x": x,
                "y": y,
                "alignment": alignment,
                "font_size": font_size if font_size else self.default_font_size,
                "font_color": color if color else self.default_text_color,
                "bg_color": bg_color if bg_color else self.default_bg_color,
                "font_name": "Noto Serif Bold"
            },
            "timeout": time.time() + timeout if timeout > 0 else -1
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
        logger.debug(
            f"upsert_triangle: {triangle_id}, {x}, {y}, {radius}, {line_width}, {line_color}, {angle}, {timeout}")
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
                self.elements[triangle_id]["timeout"] = time.time() + timeout if timeout > 0 else -1

            self.elements[triangle_id]["object"].update()

            return triangle_id

        return self.create_triangle(x, y, radius, line_width, line_color, angle, timeout, triangle_id)

    def upsert_text(self,
                    text: str,
                    text_id: Optional[str] = None,
                    x: Optional[int] = None,
                    y: Optional[int] = None,
                    alignment: Optional[str] = None,
                    font_size: Optional[int] = None,
                    color: Optional[Tuple[float, float, float, float]] = None,
                    bg_color: Optional[Tuple[float,
                                             float, float, float]] = None,
                    timeout: Optional[float] = None) -> str:
        """ Add or update a text element with the given parameters. """

        logger.debug(
            f"upsert_text: {text}, {text_id}, {x}, {y}, {alignment}, {font_size}, {color}, {bg_color}, {timeout}")

        if text_id is not None and text_id in self.elements and self.elements[text_id]["type"] == "text":
            if text is not None:
                try: 
                    text = f"{float(text):.2f}"
                except ValueError: 
                    pass    
                self.elements[text_id]["object"]["text"] = text
            if x is not None:
                self.elements[text_id]["object"]["x"] = x
            if y is not None:
                self.elements[text_id]["object"]["y"] = y
            if alignment is not None:
                self.elements[text_id]["object"]["alignment"] = alignment
            if font_size is not None:
                self.elements[text_id]["object"]["font_size"] = font_size
            if color is not None:
                self.elements[text_id]["object"]["font_color"] = color
            if bg_color is not None:
                self.elements[text_id]["object"]["bg_color"] = bg_color
            if timeout is not None:
                self.elements[text_id]["timeout"] = time.time() + timeout if timeout > 0 else -1

            return text_id

        return self.add_text(text, x, y, alignment, font_size, color, bg_color, timeout, text_id)


    '''
    "OSD": " {
        \"OSD1\":\"{
            \"text\":\"\",
            \"font_name\":
            \"Noto Serif Bold\",
            \"font_size\":\"18\",
            \"font_color\":\"1.0,1.0,1.0,1.0\",
            \"bg_color\":\"0.0,0.0,0.0,0.6\",
            \"pos_x\":\"0\",
            \"pos_y\":\"0\",
            \"timeout\":\"0\",
            \"visible\":false
            }\",
        \"OSD2\":\"{\"text\":\"\",\"font_name\":\"Noto Serif Bold\",\"font_size\":\"18\",\"font_color\":\"1.0,1.0,1.0,1.0\",\"bg_color\":\"0.0,0.0,0.0,0.6\",\"pos_x\":\"0\",\"pos_y\":\"0\",\"timeout\":\"0\",\"visible\":false}\",
        \"OSD3\":\"{\"text\":\"\",\"font_name\":\"Noto Serif Bold\",\"font_size\":\"18\",\"font_color\":\"1.0,1.0,1.0,1.0\",\"bg_color\":\"0.0,0.0,0.0,0.6\",\"pos_x\":\"0\",\"pos_y\":\"0\",\"timeout\":\"0\",\"visible\":false}\",
        \"OSD4\":\"{\"text\":\"\",\"font_name\":\"Noto Serif Bold\",\"font_size\":\"18\",\"font_color\":\"1.0,1.0,1.0,1.0\",\"bg_color\":\"0.0,0.0,0.0,0.6\",\"pos_x\":\"0\",\"pos_y\":\"0\",\"timeout\":\"0\",\"visible\":false}\"}"
    '''

    def upsert_text_from_dict(self, text_dict: Dict[str, Any], text_id: Optional[str] = None) -> str:
        """ Add or update a text element with the given parameters. """
        logger.debug(f"upsert_text_from_dict: {text_dict}, {text_id}")

        if text_id is not None and text_id in self.elements and self.elements[text_id]["type"] == "text":
            return self.upsert_text(
                text=text_dict.get("text", ""),
                text_id=text_id,
                x=int(text_dict.get("pos_x", 0)),
                y=int(text_dict.get("pos_y", 0)),
                alignment=text_dict.get("alignment", "left"),
                font_size=int(text_dict.get("font_size", 18)),
                color=tuple(map(float, text_dict.get("font_color", "1.0,1.0,1.0,1.0").split(","))),
                bg_color=tuple(map(float, text_dict.get("bg_color", "0.0,0.0,0.0,0.6").split(","))),
                timeout=float(text_dict.get("timeout", None))
            )

        return self.create_text(
            text=text_dict.get("text", ""),
            x=int(text_dict.get("pos_x", 0)),
            y=int(text_dict.get("pos_y", 0)),
            alignment=text_dict.get("alignment", "left"),
            font_size=int(text_dict.get("font_size", 18)),
            color=tuple(map(float, text_dict.get("font_color", "1.0,1.0,1.0,1.0").split(","))),
            bg_color=tuple(map(float, text_dict.get("bg_color", "0.0,0.0,0.0,0.6").split(","))),
            timeout=float(text_dict.get("timeout", None)),
            text_id=text_id
        )



    def remove_element(self, element_id: str):
        if element_id in self.elements:
            del self.elements[element_id]

    def _cleanup_expired_elements(self, current_time: float):
        self.elements = {element_id: element for element_id, element in self.elements.items(
        ) if element["timeout"] is None or element["timeout"] < 0 or element["timeout"] > current_time}

    def get_all_lines_as_dicts(self) -> List[Dict]:
        lines = []
        for element in self.elements.values():
            if element["type"] == "triangle" or element["type"] == "polygon":
                lines.extend(element["object"].to_lines())
        return [line.to_dict_ints() for line in lines]

    def get_all_texts(self) -> List[Dict]:
        return [element["object"] for element in self.elements.values() if element["type"] == "text"]
