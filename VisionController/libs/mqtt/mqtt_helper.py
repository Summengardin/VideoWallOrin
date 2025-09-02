from typing import List

def validate_mqtt_structure(config: dict) -> None:
    """
    Validates the minimum required MQTT topic structure.
    Raises ValueError if validation fails.
    """
    required_sections = {
        'cameras': ['names', 'subtopics'],
        'vision_controllers': ['names', 'subtopics', 'tiles']
    }

    if not isinstance(config, dict):
        raise ValueError("Configuration must be a dictionary")

    for section, required_keys in required_sections.items():
        if section not in config:
            raise ValueError(f"Missing required section: {section}")
            
        section_data = config[section]
        if not isinstance(section_data, dict):
            raise ValueError(f"Section {section} must be a dictionary, but got {type(section_data)}")
            
        for key in required_keys:
            if key not in section_data:
                raise ValueError(f"Missing required key '{key}' in section '{section}'")
            
            if key in ['names', 'subtopics']:
                if not isinstance(section_data[key], list):
                    raise ValueError(f"'{section}.{key}' must be a list, but got {type(section_data[key])}")
                if not section_data[key]:
                    raise ValueError(f"'{section}.{key}' cannot be empty")

    # Validate tiles structure
    tiles = config['vision_controllers'].get('tiles')
    if not isinstance(tiles, dict):
        raise ValueError("'tiles' must be a dictionary")
    if 'names' not in tiles or 'subtopics' not in tiles:
        raise ValueError("'tiles' must contain 'names' and 'subtopics'")
    if not isinstance(tiles['names'], list) or not isinstance(tiles['subtopics'], list):
        raise ValueError("'tiles.names' and 'tiles.subtopics' must be lists, but got {type(tiles['names'])} and {type(tiles['subtopics'])}")
    if not tiles['names'] or not tiles['subtopics']:
        raise ValueError("'tiles.names' and 'tiles.subtopics' cannot be empty")
    

def load_mqtt_topics(config: dict) -> List[str]:
    """
    generate all subscription topics.
    Returns a list of topic strings.
    """
    topics = []
    validate_mqtt_structure(config)

    def append_subtopic_with_qos(subtopic, base_topic):
        if isinstance(subtopic, dict):
            topic = next(iter(subtopic))
            qos = subtopic[topic]
            topics.append((f"{base_topic}/{topic}", qos))
        else:
            topics.append((f"{base_topic}/{subtopic}", 0))

    base_topic = "VWController"
    # Generate camera topics
    camera_config = config['cameras']
    for camera_name in camera_config['names']:
        base_cam_topic = f"{base_topic}/Cameras/{camera_name}"
        for subtopic in camera_config['subtopics']:
            append_subtopic_with_qos(subtopic, base_cam_topic)
    # camera_config = config['cameras']
    # for camera_name in camera_config['names']:
    #     topic = f"{base_topic}/Cameras/{camera_name}"
    #     topics.append((topic, 0))
    

    # Generate vision controller topics
    vc_config = config['vision_controllers']
    for vc_name in vc_config['names']:
        base_vc_topic = f"{base_topic}/VisionControllers/{vc_name}"
        
        # Add main controller topics
        for subtopic in vc_config['subtopics']:
            append_subtopic_with_qos(subtopic, base_topic)
        
        # Add tile topics
        tile_config = vc_config['tiles']
        for tile_name in tile_config['names']:
            topic = f"{base_vc_topic}/{tile_name}"
            topics.append((topic, 0))
            for subtopic in tile_config['subtopics']:
                append_subtopic_with_qos(subtopic, topic)

    return topics



if __name__ == "__main__":
    import yaml

    config_file = '/home/seaonics/Dev/VideoWallOrin/VisionController/config/config.yml'

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    mqtt_config = config['mqtt']
    topics = load_mqtt_topics(mqtt_config)

    for topic, qos in topics:
        print(f"Topic: {topic}, QoS: {qos}")
   