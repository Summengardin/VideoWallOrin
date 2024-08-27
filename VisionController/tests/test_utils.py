import pytest
import yaml
from fractions import Fraction
from pathlib import Path
from dataclasses import dataclass
from VisionController.libs.utils import (
    find_digits_in_string, 
    index_dataclass, 
    parse_config, 
    float_to_fraction, 
    scale, 
    clamp, 
    get_center_position_of_text_on_screen,
    build_triangle
)

def test_find_digits_in_string():
    assert find_digits_in_string("abc123def") == 123
    with pytest.raises(ValueError):
        find_digits_in_string("no digits")

@dataclass
class SampleDataClass:
    field1: int
    field2: str

def test_index_dataclass():
    data = [SampleDataClass(1, "a"), SampleDataClass(2, "b"), SampleDataClass(3, "c")]
    assert index_dataclass(data, "field1", 2) == 1
    assert index_dataclass(data, "field2", "c") == 2
    with pytest.raises(ValueError):
        index_dataclass(data, "field1", 4)

def test_parse_config(tmp_path):
    config_content = """
    key1: value1
    key2: value2
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content)
    
    config = parse_config(config_path)
    assert config == {"key1": "value1", "key2": "value2"}

def test_float_to_fraction():
    assert float_to_fraction(0.5) == (1, 2)
    assert float_to_fraction(0.75) == (3, 4)
    assert float_to_fraction(1.333, 100) == (4, 3)

def test_scale():
    assert scale(0.5, 0, 1, 0, 100) == 50
    assert scale(25, 0, 50, 0, 10) == 5
    assert scale(10, 0, 20, 100, 200) == 150

def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(15, 0, 10) == 10

def test_get_center_position_of_text_on_screen():
    assert get_center_position_of_text_on_screen(10, 12, 800, 600) == (340, 288)
    assert get_center_position_of_text_on_screen(20, 24, 1024, 768) == (272, 360)

# def test_build_triangle():
#     assert build_triangle((0, 0), 20, 0) == [(10, 10), (20, 10), (15, 20)]

