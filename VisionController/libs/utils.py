import re
import yaml
from fractions import Fraction

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


def scale(value, from_min = 0, from_max = 1, to_min = 0, to_max = 100):
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


def clamp(value, lower, upper):
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
    Get the center position of a string on the screen.

    :param string_length: The length of the string.
    :param font_size: The size of the font.
    :param window_x: The x-coordinate of the window.
    :param window_y: The y-coordinate of the window.
    :return: The x and y coordinates of the center of the string.
    """
    return window_x // 2 - string_length // 2, window_y // 2 - font_size