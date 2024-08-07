import sys
import logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format='%(asctime)s [%(levelname)s] %(name)s:  %(message)s')

from VisionController import app




if __name__ == "__main__":
    app.run()