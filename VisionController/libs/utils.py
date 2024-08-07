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