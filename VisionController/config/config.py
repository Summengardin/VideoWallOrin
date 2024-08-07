import yaml

def parse_config(config_file):
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config

class Config:
    def __init__(self, config_file):
        self.config = parse_config(config_file)
        self.mqtt_config = self.config['mqtt']
        self.pipeline_config = self.config['pipeline']
        