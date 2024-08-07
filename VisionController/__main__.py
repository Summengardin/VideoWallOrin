import sys
import argparse
import logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format='%(asctime)s [%(levelname)s] %(name)s:  %(message)s')

from VisionController.app import App

parser = argparse.ArgumentParser()
parser.add_argument('--config', '-c', type=str, default='./VisionController/config/config.yml')



if __name__ == "__main__":

    args = parser.parse_args()
    config_file = args.config

    app = App(config_file=config_file)
    app.run()