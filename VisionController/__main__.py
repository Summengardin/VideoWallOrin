
import sys
import argparse
import logging
import time
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format='%(asctime)s [%(levelname)s] %(name)s:  %(message)s')

from VisionController.app import App

parser = argparse.ArgumentParser()
parser.add_argument('--config', '-c', type=str, default='./VisionController/config/config.yml')



if __name__ == "__main__":

    args = parser.parse_args()
    app = App(config_file=args.config)

    app.run()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    app.stop()





