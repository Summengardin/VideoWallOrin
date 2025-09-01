import sys
import argparse
import time
import signal
import logging
import threading
import faulthandler
faulthandler.enable()

from VisionController.app import App

parser = argparse.ArgumentParser()
parser.add_argument('--config', '-c', type=str, default='./VisionController/config/config_vwcontroller.yml')
parser.add_argument('--log-level', '-l', type=str, default='DEBUG', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help='Set the logging level')
parser.add_argument('--log-file', '-f', type=str, default=None, help='Set the log file path. If not provided, logs will be printed to stdout.')
args = parser.parse_args()

if args.log_file:
    logging.basicConfig(filename=args.log_file, format='%(asctime)s [%(levelname)s] %(name)s:  %(message)s')
else:
    logging.basicConfig(stream=sys.stdout, format='%(asctime)s [%(levelname)s] %(name)s:  %(message)s')

try:
    log_level = getattr(logging, args.log_level)
except AttributeError:
    print(f"Invalid log level: {args.log_level}, using DEBUG")
    log_level = logging.DEBUG

logging.getLogger().setLevel(log_level)

# Global shutdown event
shutdown_event = threading.Event()

def handle_shutdown(signum, frame):
    """Handle shutdown signals"""
    logging.info(f"Received signal {signum}, initiating shutdown...")
    shutdown_event.set()

def handle_window_close(app):
    """Handle window close event from pipeline"""
    logging.info("Window close detected, initiating shutdown...")
    shutdown_event.set()

if __name__ == "__main__":
    try:
        app = App(config_file=args.config)
        
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
        
        app.pipeline_manager.set_window_close_callback(lambda: handle_window_close(app))
        app.pipeline_manager.set_shutdown_callback(lambda: shutdown_event.set())
        
        app.run()
        
        while not shutdown_event.is_set():
            time.sleep(0.1)
            
        logging.info("Shutdown initiated, stopping application...")
        
    except Exception as e:
        logging.exception(f"Unhandled exception occurred: {e}")
        shutdown_event.set()
        
    finally:
        app.stop()
        logging.info("Shutdown complete. Goodbye!")




