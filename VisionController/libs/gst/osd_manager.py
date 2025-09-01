from VisionController.libs.utils import build_triangle, check_points_inside_frame, move_vertices_inside_frame
from VisionController.libs.material_symbols import material_symbols
import time
import threading
from typing import Tuple, List, Dict, Any, Optional
import math
from itertools import pairwise



import logging
logger = logging.getLogger(__name__)


DEFAULT_FONT_NAME = "Noto Serif Bold"
DEFAULT_SYMBOL_FONT_NAME = "MaterialSymbolsOutlined-Medium"

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

class Rectangle: 
    def __init__(self, x: int, y: int, width: int, height: int, border_width: int, border_color: tuple, bg_color: Optional[tuple] = None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.border_width = border_width
        self.border_color = border_color
        self.bg_color = bg_color

    def to_lines(self) -> List[Line]:
        lines = []
        corners = [
            (self.x, self.y),
            (self.x + self.width, self.y),
            (self.x + self.width, self.y + self.height),
            (self.x, self.y + self.height)
        ]
        for (x1, y1), (x2, y2) in pairwise(corners + [corners[0]]):
            lines.append(Line(x1, y1, x2, y2, self.border_width, self.border_color))
        return lines
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "border_width": self.border_width,
            "border_color": self.border_color,
            "bg_color": self.bg_color
        }

class Triangle:
    def __init__(self, x: int, y: int, radius: int, border_width: int, border_color: tuple, angle: float = 0):
        self.x = x
        self.y = y
        self.radius = radius
        self.border_width = border_width
        self.border_color = border_color
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
                Line(x1, y1, x2, y2, self.border_width, self.border_color))
        return lines


class Polygon:
    def __init__(self, vertices: List[Tuple[int, int]], border_width: int, color: Tuple[float, float, float, float]):
        self.vertices = vertices
        self.border_width = border_width
        self.color = color

    def to_lines(self) -> List[Line]:
        lines = []
        num_vertices = len(self.vertices)
        for i in range(num_vertices):
            x1, y1 = self.vertices[i]
            x2, y2 = self.vertices[(i + 1) % num_vertices]
            lines.append(Line(x1, y1, x2, y2, self.border_width, self.color))
        return lines
    
class Text:
    def __init__(self, x: int, y: int, text: str, alignment: str, font_name: str, font_size: int,  font_color: Tuple[float, float, float, float], bg_color: Optional[Tuple[float, float, float, float]] = None):
        self.x = x
        self.y = y
        self.text = text
        self.alignment = alignment
        self.font_name = font_name
        self.font_size = font_size
        self.color = font_color
        self.bg_color = bg_color

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "text": self.text,
            "alignment": self.alignment,
            "font_size": self.font_size,
            "font_name": self.font_name,
            "font_color": self.color,
            "bg_color": self.bg_color
        }

class Symbol:
    def __init__(self, x: int, y: int, symbol: str, font_size: int, font_name: str, color: Tuple[float, float, float, float], bg_color: Optional[Tuple[float, float, float, float]] = None):
        self.x = x
        self.y = y
        self.symbol = symbol
        self.font_size = font_size
        self.font_name = font_name
        self.color = color
        self.bg_color = bg_color
        self.x_offset = font_size // 2
        self.y_offset = font_size // 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "symbol": self.symbol,
            "font_size": self.font_size,
            "font_name": self.font_name,
            "font_color": self.color,
            "bg_color": self.bg_color,
            "x_offset": self.x_offset,
            "y_offset": self.y_offset
        }



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

        self.default_font_color = (1.0, 1.0, 1.0, 1.0)
        self.default_line_color = (1.0, 0.0, 0.0, 1.0)
        self.default_border_color = (1.0, 0.0, 0.0, 1.0)
        self.default_bg_color = (0.0, 0.0, 0.0, 0.6)
        self.default_font_size = 18
        self.default_font_name = DEFAULT_FONT_NAME
        self.default_symbol_font_name = DEFAULT_SYMBOL_FONT_NAME

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

    def create_triangle(self, x: int, y: int, radius: int, line_width: int, line_color: Tuple[float, float, float, float], angle: float = 0, timeout: Optional[float] = -1, triangle_id: Optional[str] = None) -> str:
        # vertices = build_triangle((x, y), radius, angle)
        if triangle_id is None:
            triangle_id = self._generate_id()
        self.elements[triangle_id] = {
            "type": "triangle",
            "object": Triangle(x, y, radius, border_width, border_color, angle),
            "object": Triangle(x, y, radius, line_width, line_color, angle),
            "timeout": time.time() + timeout if timeout > 0 else -1,
            "visible": True
        }
        return triangle_id

    def create_polygon(self, vertices: List[Tuple[int, int]], line_width: int, line_color: Tuple[float, float, float, float], timeout: Optional[float] = -1, polygon_id: Optional[str] = None) -> str:
        if polygon_id is None:
            polygon_id = self._generate_id()
        self.elements[polygon_id] = {
            "type": "polygon",
            "object": Polygon(vertices, border_width, border_color),
            "object": Polygon(vertices, line_width, line_color),
            "timeout": time.time() + timeout if timeout > 0 else -1,
            "visible": True
        }

        return polygon_id

    def create_text(self, text: str = "", 
                            x: int = 0, 
                            y: int = 0, 
                            alignment: str = "left", 
                            font_name: str = DEFAULT_FONT_NAME,
                            font_size: int = None,
                            font_color: Tuple[float, float, float, float] = None, 
                            bg_color: Tuple[float, float, float, float] = None, 
                            timeout: Optional[float] = -1, 
                            text_id: Optional[str] = None) -> str:
        if text_id is None:
            text_id = self._generate_id()
        try:
            text = f"{float(text):.2f}"
        except ValueError:
            pass
        self.elements[text_id] = {
            "type": "text",
            "object": Text(
                x,
                y,
                text,
                alignment,
                font_name if font_name != "" else self.default_font_name,
                font_size,
                font_color,
                bg_color
            ),
            "timeout": time.time() + timeout if timeout > 0 else -1,
            "visible": True
        }
        return text_id
    

    def create_rectangle(self, x: int, y: int, width: int, height: int, border_width: int, border_color: Tuple[float, float, float, float], bg_color: Optional[Tuple[float, float, float, float]] = None, enable: bool = False, rectangle_id: Optional[str] = None) -> str:
        if rectangle_id is None:
            rectangle_id = self._generate_id()
        self.elements[rectangle_id] = {
            "type": "rectangle",
            "object": Rectangle(x, y, width, height, border_width, border_color, bg_color),
            "enable": enable
        }
        return rectangle_id
 
    
    def create_symbol(self, symbol: str,
                      x: int = 0,
                      y: int = 0,
                      font_name: str = DEFAULT_SYMBOL_FONT_NAME,
                      font_size: int = 40,
                      color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
                      bg_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.6),
                      timeout: Optional[float] = -1,
                      symbol_id: Optional[str] = None) -> str:
        if symbol_id is None:
            symbol_id = self._generate_id()

        try:
            symbol_codepoint = material_symbols[symbol]
        except KeyError:
            logger.error(f"Symbol '{symbol}' not found in material_symbols.")
            return ""
        
        self.elements[symbol_id] = {
            "type": "symbol",
            "object": Symbol(
                x=x,
                y=y,
                symbol=symbol_codepoint,
                font_size=font_size,
                font_name=font_name,
                color=color,
                bg_color=bg_color
            ),
            "timeout": time.time() + timeout if timeout > 0 else -1,
            "visible": True
        }
        return symbol_id

    def update_triangle(self, element_id: str, x: int, y: int, radius: int, line_width: int, line_color: Tuple[float, float, float, float], angle: float = 0):
        if element_id in self.elements and self.elements[element_id]["type"] == "triangle":
            vertices = build_triangle((x, y), radius, angle)
            self.elements[element_id]["object"] = Triangle(
                vertices, line_width, line_color)

    def update_polygon(self, element_id: str, vertices: List[Tuple[int, int]], line_width: int, line_color: Tuple[float, float, float, float]):
        if element_id in self.elements and self.elements[element_id]["type"] == "polygon":
            self.elements[element_id]["object"] = Polygon(
                vertices, border_width, border_color)

    def upsert_text(self, 
                    text_id: Optional[str] = None,
                    text: Optional[str] = None,
                    x: Optional[int] = None,
                    y: Optional[int] = None,
                    alignment: Optional[str] = None,
                    font_name: Optional[str] = None,
                    font_size: Optional[int] = None,
                    font_color: Optional[Tuple[float, float, float, float]] = None,
                    bg_color: Optional[Tuple[float, float, float, float]] = None,
                    timeout: Optional[float] = None) -> str:
        """ Update or create a text element with the given parameters. """
        # logger.debug(f"upsert_text: {text_id}, {text}, {x}, {y}, {alignment}, {font_size}, {color}, {bg_color}")
        
        if text_id is not None and text_id in self.elements and self.elements[text_id]["type"] == "text":
            change = False
            if text is not None and text != self.elements[text_id]["object"].text:
                self.elements[text_id]["object"].text = text
                change = True
            if x is not None:
                self.elements[text_id]["object"].x = x
            if y is not None:
                self.elements[text_id]["object"].y = y
            if alignment is not None:
                self.elements[text_id]["object"].alignment = alignment
            if font_name is not None:
                self.elements[text_id]["object"].font_name = font_name if font_name != "" else self.default_font_name
            if font_size is not None:
                self.elements[text_id]["object"].font_size = font_size
            if font_color is not None:
                self.elements[text_id]["object"].font_color = font_color
            if bg_color is not None:
                self.elements[text_id]["object"].bg_color = bg_color
            if timeout is not None and change:
                self.elements[text_id]["timeout"] = time.time() + timeout if timeout > 0 else -1
                self.elements[text_id]["visible"] = True
            
            return text_id

        return self.create_text(text, x, y, alignment, font_name, font_size, font_color, bg_color, timeout, text_id)
                    

    def upsert_triangle(self,
                        triangle_id: Optional[str] = None,
                        x: Optional[int] = None,
                        y: Optional[int] = None,
                        radius: Optional[int] = None,
                        border_width: Optional[int] = None,
                        border_color: Optional[Tuple[float, float, float, float]] = None,
                        angle: Optional[float] = None,
                        timeout: Optional[float] = -1) -> str:
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
            if border_width is not None:
                self.elements[triangle_id]["object"].border_width = border_width
            if border_color is not None:
                self.elements[triangle_id]["object"].border_color = border_color
            if angle is not None:
                self.elements[triangle_id]["object"].angle = angle
            if timeout is not None:
                self.elements[triangle_id]["timeout"] = time.time() + timeout if timeout > 0 else -1
                self.elements[triangle_id]["visible"] = True

            self.elements[triangle_id]["object"].update()

            return triangle_id

    def upsert_rectangle(self,
                         rectangle_id: Optional[str] = None,
                         x: Optional[int] = None,
                         y: Optional[int] = None,
                         width: Optional[int] = None,
                         height: Optional[int] = None,
                         border_width: Optional[int] = None,  
                         border_color: Optional[Tuple[float, float, float, float]] = None,
                         bg_color: Optional[Tuple[float, float, float, float]] = None,
                         enable: Optional[bool] = None) -> str:
        """ Update or create a rectangle with the given parameters. """
        # logger.debug(f"upsert_rectangle: {rectangle_id}, {x}, {y}, {width}, {height}, {border_width}, {border_color}, {bg_color}, {enable}")
        if rectangle_id is not None and rectangle_id in self.elements and self.elements[rectangle_id]["type"] == "rectangle":
            if x is not None:
                self.elements[rectangle_id]["object"].x = x
            if y is not None:
                self.elements[rectangle_id]["object"].y = y
            if width is not None:
                self.elements[rectangle_id]["object"].width = width
            if height is not None:
                self.elements[rectangle_id]["object"].height = height
            if border_width is not None:
                self.elements[rectangle_id]["object"].border_width = border_width
            if border_color is not None:
                self.elements[rectangle_id]["object"].border_color = border_color
            if bg_color is not None:
                self.elements[rectangle_id]["object"].bg_color = bg_color
            if enable is not None:
                self.elements[rectangle_id]["enable"] = enable

            return rectangle_id

        return self.create_rectangle(x, y, width, height, border_width, border_color, bg_color, enable, rectangle_id)


    def upsert_symbol(self,
                      symbol_id: Optional[str] = None,
                      symbol: Optional[str] = None,
                      x: Optional[int] = None,
                      y: Optional[int] = None,
                      font_size: Optional[int] = None,
                      font_name: Optional[str] = None,
                      color: Optional[Tuple[float, float, float, float]] = None,
                      bg_color: Optional[Tuple[float, float, float, float]] = None,
                      timeout: Optional[float] = None) -> str:
        """ Update or create a symbol with the given parameters. """
        logger.debug(
            f"upsert_symbol: {symbol_id}, {symbol}, {x}, {y}, {font_size}, {font_name}, {color}, {bg_color}, {timeout}")
        if symbol_id is not None and symbol_id in self.elements and self.elements[symbol_id]["type"] == "symbol":
            if symbol is not None:
                try:
                    self.elements[symbol_id]["object"].symbol = material_symbols[symbol]
                except KeyError:
                    logger.error(f"Symbol '{symbol}' not found in material_symbols.")
                    return ""
            if x is not None:
                self.elements[symbol_id]["object"].x = x
            if y is not None:
                self.elements[symbol_id]["object"].y = y
            if font_size is not None:
                self.elements[symbol_id]["object"].font_size = font_size
            if font_name is not None:
                self.elements[symbol_id]["object"].font_name = font_name
            if color is not None:
                self.elements[symbol_id]["object"].color = color
            if bg_color is not None:
                self.elements[symbol_id]["object"].bg_color = bg_color
            if timeout is not None:
                self.elements[symbol_id]["timeout"] = time.time() + timeout if timeout > 0 else -1
                self.elements[symbol_id]["visible"] = True

            return symbol_id
        
        return self.create_symbol(symbol, x, y, font_name, font_size, color, bg_color, timeout, symbol_id)

    def _extract_base_key(self, key: str) -> str:
        """Extract the base key from a key that may have prefixes/suffixes."""
        # Remove any leading dots and .Value suffix
        key = key.strip('.')
        if key.endswith('.Value'):
            key = key[:-6]
        return key    

    def upsert_text_from_dict(self, text_dict: Dict[str, Any], text_id: Optional[str] = None) -> str:
        """ Add or update a text element with the given parameters. """
        # logger.debug(f"upsert_text_from_dict: {text_dict}, {text_id}")
        # Create a normalized dictionary with base keys
        normalized_dict = {}

        for key, value in text_dict.items():
            base_key = self._extract_base_key(key)
            normalized_dict[base_key] = value
        
        if normalized_dict.get("Text") is not None and isinstance(normalized_dict["Text"], str) and normalized_dict["Text"].startswith("icon:"):
            # If the text starts with "icon:", replace it with the corresponding material symbol
            # This assumes that the icon name is the part after "icon:"
            normalized_dict["Symbol"] = normalized_dict["Text"][5:]
            return self.upsert_symbol_from_dict(
                symbol_dict=normalized_dict,
                symbol_id=text_id
            )

        if text_id is not None and text_id in self.elements and self.elements[text_id]["type"] == "text":
            return self.upsert_text(
                text=normalized_dict.get("Text", ""),
                text_id=text_id,
                x=int(normalized_dict.get("PosX", 0)),
                y=int(normalized_dict.get("PosY", 0)),
                alignment=normalized_dict.get("Alignment", "left"),
                font_name=normalized_dict.get("FontName", DEFAULT_FONT_NAME),
                font_size=int(normalized_dict.get("FontSize", 18)),
                font_color=tuple(map(float, normalized_dict.get("FontColor", "1.0,1.0,1.0,1.0").split(","))),
                bg_color=tuple(map(float, normalized_dict.get("BGColor", "0.0,0.0,0.0,0.6").split(","))),
                timeout=float(normalized_dict.get("Timeout", 0))
            )

        return self.create_text(
            text=normalized_dict.get("Text", ""),
            x=int(normalized_dict.get("PosX", 0)),
            y=int(normalized_dict.get("PosY", 0)),
            alignment=normalized_dict.get("Alignment", "left"),
            font_name=normalized_dict.get("FontName", DEFAULT_FONT_NAME),
            font_size=int(normalized_dict.get("FontSize", 18)),
            font_color=tuple(map(float, normalized_dict.get("FontColor", "1.0,1.0,1.0,1.0").split(","))),
            bg_color=tuple(map(float, normalized_dict.get("BGColor", "0.0,0.0,0.0,0.6").split(","))),
            timeout=float(normalized_dict.get("Timeout", 0)),
            text_id=text_id
        )
    
    def upsert_rectangle_from_dict(self, rectangle_dict: Dict[str, Any], rectangle_id: Optional[str] = None) -> str:
        if rectangle_id is not None and rectangle_id in self.elements and self.elements[rectangle_id]["type"] == "rectangle":
            return self.upsert_rectangle(
                rectangle_id=rectangle_id,
                x=int(rectangle_dict.get("PosX", 0)),
                y=int(rectangle_dict.get("PosY", 0)), 
                width=int(rectangle_dict.get("Width", 100)),
                height=int(rectangle_dict.get("Height", 100)),
                border_width=int(rectangle_dict.get("BorderWidth", 2)),
                border_color=self.default_border_color if rectangle_dict.get("BorderColor") in [None, "0"] else tuple(map(float, rectangle_dict["BorderColor"].split(","))),
                bg_color=None if rectangle_dict.get("BGColor") in [None, "0"] else tuple(map(float, rectangle_dict["BGColor"].split(","))),
                enable=int(rectangle_dict.get("Enable", True))
            )
        return self.create_rectangle(
            x=int(rectangle_dict.get("PosX", 0)),
            y=int(rectangle_dict.get("PosY", 0)),
            width=int(rectangle_dict.get("Width", 100)),
            height=int(rectangle_dict.get("Height", 100)),
            border_width=int(rectangle_dict.get("BorderWidth", 2)),
            border_color=None if rectangle_dict.get("BorderColor") in [None, "0"] else tuple(map(float, rectangle_dict["BorderColor"].split(","))),
            bg_color=None if rectangle_dict.get("BGColor") in [None, "0"] else tuple(map(float, rectangle_dict["BGColor"].split(","))),
            rectangle_id=rectangle_id,
            enable=int(rectangle_dict.get("Enable", True))
        )
    
    def upsert_symbol_from_dict(self, symbol_dict: Dict[str, Any], symbol_id: Optional[str] = None) -> str:
        """
        Adds or updates a symbol element using parameters provided in a dictionary.
        This method normalizes the input dictionary keys to their base form, then either updates an existing symbol
        (if `symbol_id` is provided and matches an existing symbol element) or creates a new symbol element.
        The symbol parameters are extracted from the dictionary and include position, font properties, colors, and timeout.
        The symbol key should match the keys defined in `materials_symbols.py` to ensure compatibility.
        Args:
            symbol_dict (Dict[str, Any]): Dictionary containing symbol parameters. Expected keys include:
                - "Symbol": The symbol string (should match keys in materials_symbols.py).
                - "PosX": X position (int).
                - "PosY": Y position (int).
                - "FontSize": Font size (int).
                - "FontName": Font name (str).
                - "FontColor": Font color as comma-separated RGBA values (str).
                - "BGColor": Background color as comma-separated RGBA values (str).
                - "Timeout": Timeout in seconds (float).
            symbol_id (Optional[str]): Optional identifier for the symbol. If provided and matches an existing symbol,
                the symbol will be updated; otherwise, a new symbol will be created.
        Returns:
            str: The identifier of the created or updated symbol element.
        """

        # logger.debug(f"upsert_symbol_from_dict: {symbol_dict}, {symbol_id}")

        # Create a normalized dictionary with base keys
        normalized_dict = {}

        for key, value in symbol_dict.items():
            base_key = self._extract_base_key(key)
            normalized_dict[base_key] = value

        if symbol_id is not None and symbol_id in self.elements and self.elements[symbol_id]["type"] == "symbol":
            return self.upsert_symbol(
                symbol=normalized_dict.get("Symbol", ""),
                symbol_id=symbol_id,
                x=int(normalized_dict.get("PosX", 0)),
                y=int(normalized_dict.get("PosY", 0)),
                font_size=int(normalized_dict.get("FontSize", 40)),
                font_name=normalized_dict.get("FontName", DEFAULT_SYMBOL_FONT_NAME),
                color=tuple(map(float, normalized_dict.get("FontColor", "1.0,1.0,1.0,1.0").split(","))),
                bg_color=tuple(map(float, normalized_dict.get("BGColor", "0.0,0.0,0.0,0.6").split(","))),
                timeout=float(normalized_dict.get("Timeout", 0))
            )

        return self.create_symbol(
            symbol=normalized_dict.get("Symbol", ""),
            x=int(normalized_dict.get("PosX", 0)),
            y=int(normalized_dict.get("PosY", 0)),
            font_size=int(normalized_dict.get("FontSize", 40)),
            font_name=normalized_dict.get("FontName", DEFAULT_SYMBOL_FONT_NAME),
            color=tuple(map(float, normalized_dict.get("FontColor", "1.0,1.0,1.0,1.0").split(","))),
            bg_color=tuple(map(float, normalized_dict.get("BGColor", "0.0,0.0,0.0,0.6").split(","))),
            timeout=float(normalized_dict.get("Timeout", 0)),
            symbol_id=symbol_id
        )
    
    

    def remove_element(self, element_id: str):
        if element_id in self.elements:
            del self.elements[element_id]

    def _cleanup_expired_elements(self, current_time: float):
        for element in self.elements.values():
            timeout = element.get("timeout")
            if timeout is not None and timeout >= 0 and timeout <= current_time:
                element["visible"] = False

        # self.elements = {element_id: element for element_id, element in self.elements.items(
        # ) if element["timeout"] is None or element["timeout"] < 0 or element["timeout"] > current_time}

    def get_all_lines_as_dicts(self) -> List[Dict]:
        lines = []
        for element in self.elements.values():
            if element["type"] == "triangle" or element["type"] == "polygon":
                lines.extend(element["object"].to_lines())
        return [line.to_dict_ints() for line in lines]

    def get_all_texts_as_dicts(self) -> List[Dict]:
        return [element["object"].to_dict() for element in self.elements.values() if (element["type"] == "text" and element["visible"] == True)]

    def get_all_symbols_as_dicts(self) -> List[Dict]:
    def get_all_rectangles_as_dicts(self) -> List[Dict]:
        return [element["object"].to_dict() for element in self.elements.values() if ((element["type"] == "rectangle") and element["enable"])]