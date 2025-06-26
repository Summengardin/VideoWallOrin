import sys
import argparse
import time
import signal
import logging
import threading

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
    numeric_level = getattr(logging, args.log_level)
except AttributeError:
    print(f"Invalid log level: {args.log_level}, using DEBUG")
    numeric_level = logging.DEBUG

logging.getLogger().setLevel(numeric_level)

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
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
        
        # Set window close callback
        app.pipeline_manager.set_window_close_callback(lambda: handle_window_close(app))
        
        # Start the application
        app.run()
        
        # Main loop - wait for shutdown event
        while not shutdown_event.is_set():
            time.sleep(0.1)  # Reduced sleep time for more responsive shutdown
            
        logging.info("Shutdown initiated, stopping application...")
        
    except Exception as e:
        logging.exception(f"Unhandled exception occurred: {e}")
        shutdown_event.set()
        
    finally:
        if 'app' in locals():
            logging.info("Stopping the app...")
            app.stop()
        logging.info("Shutdown complete. Goodbye!")




