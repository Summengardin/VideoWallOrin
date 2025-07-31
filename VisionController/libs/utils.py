import re
import yaml
import math
from fractions import Fraction
from shapely.geometry import LineString, Point, Polygon
import numpy as np
from typing import Any, List


def find_digits_in_string(string: str) -> int:
    """
    Find all digits in a string and return them as an integer.

    :param string: The string to search for digits.
    :return: The integer value of the first found digit in the string.
    :raises ValueError: If no digits are found in the string.
    """
    match = re.search(r'\d+', string)
    if match:
        return int(match.group())
    
    raise ValueError("No digits found in string")


def index_dataclass(dataclass_list: List[Any], field_name: str, value: Any) -> int:
    """
    Find the index of the first dataclass instance in the list that matches the given field value.
    
    :param dataclass_list: List of dataclass instances.
    :param field_name: The name of the field to search for.
    :param value: The value to search for.
    :return: Index of the first matching dataclass instance.
    :raises ValueError: If no dataclass instance with the specified field value is found.
    """
    for index, item in enumerate(dataclass_list):
        if getattr(item, field_name) == value:
            return index
    raise ValueError(f"No dataclass instance with field '{field_name}' = {value}")


def parse_config(config_path: str) -> dict:
    """
    Parse a YAML config file and return the contents as a dictionary.

    :param config_path: Path to the config file.
    :return: Dictionary containing the config file contents.
    """
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
        return config


def float_to_fraction(float_number, max_denominator=1000) -> tuple[int, int]:
    """
    Convert a float to its best fraction representation.

    :param float_number: The float number to be converted.
    :param max_denominator: The maximum value for the denominator.
    :return: A tuple containing the numerator and denominator.
    """
    fraction = Fraction(float_number).limit_denominator(max_denominator)
    return fraction.numerator, fraction.denominator


def scale(value, from_min = 0.0, from_max = 1.0, to_min = 0.0, to_max = 100.0):
    """
    Scale a value from one range to another.

    :param value: The value to scale.
    :param from_min: The minimum value of the original range.
    :param from_max: The maximum value of the original range.
    :param to_min: The minimum value of the target range.
    :param to_max: The maximum value of the target range.
    :return: The scaled value.
    """
    return (value - from_min) * (to_max - to_min) / (from_max - from_min) + to_min


def clamp(value, lower=0.0, upper=1.0):
    """
    Clamp a value between a minimum and maximum value.

    :param value: The value to clamp.
    :param lower: The minimum value.
    :param upper: The maximum value.
    
    :return: The clamped value.
    """
    return lower if value < lower else upper if value > upper else value


def get_center_position_of_text_on_screen(string_length: int, font_size: int, window_x: int, window_y: int) -> tuple[int, int]:
    """
    Get the center position of a string on the screen. Very simplified function.

    :param string_length: The length of the string.
    :param font_size: The size of the font.
    :param window_x: The x-coordinate of the window.
    :param window_y: The y-coordinate of the window.
    :return: The x and y coordinates of the center of the string.
    """
    return (window_x - string_length * font_size) // 2, window_y // 2 - font_size


def build_triangle(center: tuple[int, int], radius: int, angle: float, angle_deg = True) -> List[tuple[int, int]]:
    """
    Build a triangle with the given center, radius, and angle.

    :param center: The center of the triangle.
    :param radius: The radius of the triangle.
    :param angle: The angle of the triangle (in radians).
    :return: The vertices of the triangle.
    """

    if angle_deg:
        angle = math.radians(angle)

    tri = []
    for i in range(3):
        x = center[0] + radius * math.cos(angle + i * 2 * math.pi / 3)
        y = center[1] + radius * math.sin(angle + i * 2 * math.pi / 3)
        tri.append((int(x), int(y)))
    return tri


def calculate_text_offset(text: str, font_size: int, alignment: str) -> int:
    """
    Calculate the offset to align text either to the right or center based on the length of the string and font size.

    :param str text: The text to be aligned.
    :param int font_size: The font size used for the text.
    :param str alignment: The desired alignment ('center','c' or 'right','r').
    :return: The calculated offset.
    :rtype: int
    """
    # Estimate the width of the text based on its length and the font size
    estimated_text_width = len(text) * (font_size // 1.1)
    
    alignment = alignment.lower()
    if alignment == 'center' or alignment == 'c':
        # Calculate the offset to center the text
        offset = -estimated_text_width // 2
    elif alignment == 'right' or alignment == 'r':
        # Calculate the offset to align the text to the right
        offset = -estimated_text_width
    elif alignment == 'left' or alignment == 'l':
        # No offset needed for left alignment
        offset = 0
    elif alignment == None:
        # No offset needed for left alignment
        offset = 0
    else:
        raise ValueError(f"on '{alignment}'. Alignment must be either 'left', 'center' or 'right'.")

    return int(offset)


def check_points_inside_frame(vertices: List[tuple[int, int]], window_x: int, window_y: int) -> bool:
    """
    Check if the vertices are inside the frame.

    :param vertices: The vertices to check.
    :param window_x: The x-coordinate of the window.
    :param window_y: The y-coordinate of the window.
    :return: True if the vertices are inside the frame, False otherwise.    
    """

    # Create the frame polygon
    frame_polygon = Polygon([(0, 0), (window_x, 0), (window_x, window_y), (0, window_y)])

    # Check if the vertices are inside the frame
    for vertex in vertices:
        if not frame_polygon.contains(Point(vertex)):
            return False
    return True

def move_vertices_inside_frame(vertices: List[tuple[int, int]], frame: tuple[int, int, int, int]) -> List[tuple[int, int]]:
    """
    Check if the vertices are inside the frame and create new vertices at the intersection points.

    :param vertices: List of tuples representing the vertices of the shape [(x1, y1), (x2, y2), ...]
    :param frame: Tuple representing the frame (x_min, y_min, x_max, y_max)
    :return: List of updated vertices
    """
    x_min, y_min, x_max, y_max = frame

    # Create the frame polygon
    frame_polygon = Polygon([(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)])

    updated_vertices = []

    # Convert frame edges to a list
    frame_edges = list(frame_polygon.exterior.coords)

    # Loop through the edges of the shape
    for i in range(len(vertices)):
        # Get the current and next vertex (to form a line segment)
        start_vertex = Point(vertices[i])
        end_vertex = Point(vertices[(i + 1) % len(vertices)])

        # Check if both points are inside the frame
        if frame_polygon.contains(start_vertex) and frame_polygon.contains(end_vertex):
            updated_vertices.append((start_vertex.x, start_vertex.y))

        else:
            # If any point is outside, create a line segment and find intersections with frame
            line = LineString([start_vertex, end_vertex])
            
            # Add starting vertex if it is inside the frame
            if frame_polygon.contains(start_vertex):
                updated_vertices.append((start_vertex.x, start_vertex.y))
            
            # Find intersections with frame borders
            for j in range(len(frame_edges) - 1):  # Loop through frame edges
                edge_start = Point(frame_edges[j])
                edge_end = Point(frame_edges[(j + 1) % len(frame_edges)])
                frame_line = LineString([edge_start, edge_end])
                
                # Check for intersection between shape edge and frame edge
                if line.intersects(frame_line):
                    intersection = line.intersection(frame_line)
                    if not intersection.is_empty:
                        updated_vertices.append((intersection.x, intersection.y))
            
            # Add ending vertex if it is inside the frame
            if frame_polygon.contains(end_vertex):
                updated_vertices.append((end_vertex.x, end_vertex.y))

    return updated_vertices



        

