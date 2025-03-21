import pytest
import yaml
from typing import Dict

from VisionController.libs.mqtt.mqtt_helper import (
    load_mqtt_topics, 
    validate_mqtt_structure
)



@pytest.fixture
def valid_config() -> Dict:
    return {
        'cameras': {
            'names': ['Camera0', 'Camera1'],
            'subtopics': ['IP', 'Type']
        },
        'vision_controllers': {
            'names': ['VisionController0'],
            'subtopics': ['IP', 'Width'],
            'tiles': {
                'names': ['Tile01'],
                'subtopics': ['Source', 'Enable']
            }
        }
    }

@pytest.fixture
def invalid_configs():
    return [
        {},  # Empty config
        {'cameras': {}},  # Missing required keys
        {'cameras': {'names': [], 'subtopics': []}},  # Empty lists
        {'cameras': {'names': 'not_a_list', 'subtopics': ['IP']}},  # Invalid type
        {'vision_controllers': {
            'names': ['VC0'],
            'subtopics': ['IP'],
            'tiles': 'not_a_dict'
        }}  # Invalid tiles type
    ]

def test_validate_valid_config(valid_config):
    validate_mqtt_structure(valid_config)  # Should not raise

def test_validate_invalid_configs(invalid_configs):
    for config in invalid_configs:
        with pytest.raises(ValueError):
            validate_mqtt_structure(config)

def test_load_mqtt_topics_structure(valid_config):
    topics = load_mqtt_topics(valid_config)
    assert isinstance(topics, list)
    assert all(isinstance(t, tuple) and len(t) == 2 for t in topics)
    assert all(isinstance(t[0], str) and isinstance(t[1], int) for t in topics)

def test_topic_patterns(valid_config):
    topics = load_mqtt_topics(valid_config)
    
    # Test camera topics
    camera_topics = [t[0] for t in topics if t[0].startswith('Cameras/')]
    assert any(t.startswith('Cameras/Camera0/') for t in camera_topics)
    assert any(t.startswith('Cameras/Camera1/') for t in camera_topics)
    
    # Test vision controller topics
    vc_topics = [t[0] for t in topics if t[0].startswith('VisionControllers/')]
    assert any(t.startswith('VisionControllers/VisionController0/') for t in vc_topics)
    assert any(t.endswith('/Tile01/Source') for t in vc_topics)

def test_qos_values(valid_config):
    topics = load_mqtt_topics(valid_config)
    assert all(qos in [0, 1, 2] for _, qos in topics)

if __name__ == '__main__':
    pytest.main([__file__])