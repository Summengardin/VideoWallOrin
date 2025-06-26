#!/usr/bin/env python3

import argparse
import sys
import threading
import time
import datetime
import gi
import signal
import os
from typing import Dict, List
from dataclasses import dataclass
from queue import Queue

# Initialize GStreamer
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject

Gst.init(None)

@dataclass
class RecordingPipeline:
    pipeline: Gst.Pipeline
    bus: Gst.Bus
    uri: str
    filename: str
    thread: threading.Thread
    is_running: bool = True

class RTSPRecorder:
    def __init__(self, output_dir: str = None):
        self.pipelines: Dict[str, RecordingPipeline] = {}
        self.shutdown_event = threading.Event()
        self.error_queue = Queue()
        self.output_dir = output_dir
        
        # Create output directory if it doesn't exist
        if self.output_dir:
            os.makedirs(self.output_dir, exist_ok=True)
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\nReceived signal {signum}, initiating graceful shutdown...")
        self.shutdown_event.set()

    def _create_pipeline(self, uri: str) -> RecordingPipeline:
        """Create a new GStreamer pipeline for recording"""
        now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        uri_safe = uri.replace('rtsp://', '').replace('/', '_').replace(':', '_')
        filename = f"{uri_safe}_{now}.mkv"
        
        # If output directory is specified, prepend it to the filename
        if self.output_dir:
            filename = os.path.join(self.output_dir, filename)

        pipeline_str = (
            f"uridecodebin uri={uri} ! nvvideoconvert ! "
            "videoconvert ! "
            "clockoverlay time-format=\"%Y-%m-%d %H:%M:%S\" "
            "halignment=left valignment=top shaded-background=true font-desc=\"12\" ! "
            "x264enc speed-preset=ultrafast tune=zerolatency bitrate=5000 ! "
            "h264parse config-interval=1 ! "
            "matroskamux ! "
            f"filesink location=\"{filename}\" sync=false"
        )

        pipeline = Gst.parse_launch(pipeline_str)
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self._bus_message_handler, uri)

        return RecordingPipeline(
            pipeline=pipeline,
            bus=bus,
            uri=uri,
            filename=filename,
            thread=threading.Thread(target=self._pipeline_thread, args=(uri,), daemon=True)
        )

    def _bus_message_handler(self, bus: Gst.Bus, message: Gst.Message, uri: str):
        """Handle GStreamer bus messages"""
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, dbg = message.parse_error()
            self.error_queue.put((uri, f"Pipeline error: {err.message if err else err} - {dbg}"))
        elif t == Gst.MessageType.EOS:
            self.error_queue.put((uri, "Pipeline reached end of stream"))
        elif t == Gst.MessageType.STATE_CHANGED:
            old, new, pending = message.parse_state_changed()
            if message.src == self.pipelines[uri].pipeline:
                self.error_queue.put((uri, f"Pipeline state changed from {old.value_nick} to {new.value_nick}"))

    def _pipeline_thread(self, uri: str):
        """Thread function to manage a single pipeline"""
        pipeline_info = self.pipelines[uri]
        
        while not self.shutdown_event.is_set() and pipeline_info.is_running:
            try:
                # Start the pipeline
                ret = pipeline_info.pipeline.set_state(Gst.State.PLAYING)
                if ret == Gst.StateChangeReturn.FAILURE:
                    self.error_queue.put((uri, "Failed to start pipeline"))
                    time.sleep(5)
                    continue

                print(f"[{uri}] Started recording to {pipeline_info.filename}")

                # Monitor pipeline state
                while not self.shutdown_event.is_set() and pipeline_info.is_running:
                    # Check pipeline state
                    state = pipeline_info.pipeline.get_state(Gst.SECOND)
                    if state[0] == Gst.StateChangeReturn.FAILURE:
                        self.error_queue.put((uri, "Pipeline state change failed"))
                        break

                    # Check for messages
                    msg = pipeline_info.bus.timed_pop_filtered(
                        Gst.SECOND,
                        Gst.MessageType.ERROR | Gst.MessageType.EOS | Gst.MessageType.STATE_CHANGED
                    )
                    
                    if msg:
                        if msg.type == Gst.MessageType.ERROR:
                            err, dbg = msg.parse_error()
                            self.error_queue.put((uri, f"Pipeline error: {err.message if err else err} - {dbg}"))
                            break
                        elif msg.type == Gst.MessageType.EOS:
                            self.error_queue.put((uri, "Pipeline reached end of stream"))
                            break

                    time.sleep(1)

            except Exception as e:
                self.error_queue.put((uri, f"Pipeline error: {str(e)}"))
                time.sleep(5)  # Wait before retrying

            finally:
                # Clean up pipeline
                if pipeline_info.pipeline:
                    pipeline_info.pipeline.set_state(Gst.State.NULL)
                    # Create new pipeline for next attempt
                    pipeline_info = self._create_pipeline(uri)
                    self.pipelines[uri] = pipeline_info

            # If we're not shutting down, wait before retrying
            if not self.shutdown_event.is_set():
                print(f"[{uri}] Reconnecting in 5s...")
                time.sleep(5)

    def start_recording(self, uris: List[str]):
        """Start recording all URIs"""
        for uri in uris:
            if uri not in self.pipelines:
                pipeline_info = self._create_pipeline(uri)
                self.pipelines[uri] = pipeline_info
                pipeline_info.thread.start()
                print(f"[{uri}] Started recording thread")

    def stop_recording(self):
        """Gracefully stop all recordings"""
        print("\nStopping all recordings...")
        
        # First, send EOS to all pipelines
        for uri, pipeline_info in self.pipelines.items():
            if pipeline_info.pipeline:
                print(f"[{uri}] Sending EOS...")
                pipeline_info.pipeline.send_event(Gst.Event.new_eos())
                pipeline_info.is_running = False

        # Wait for pipelines to finish
        for uri, pipeline_info in self.pipelines.items():
            if pipeline_info.thread.is_alive():
                print(f"[{uri}] Waiting for pipeline to finish...")
                pipeline_info.thread.join(timeout=10)
                
                # Force stop if still running
                if pipeline_info.thread.is_alive():
                    print(f"[{uri}] Force stopping pipeline...")
                    if pipeline_info.pipeline:
                        pipeline_info.pipeline.set_state(Gst.State.NULL)

        print("All recordings stopped")

    def run(self, uris: List[str]):
        """Main run loop"""
        try:
            self.start_recording(uris)
            
            # Main loop
            while not self.shutdown_event.is_set():
                # Check for errors
                try:
                    while not self.error_queue.empty():
                        uri, error = self.error_queue.get_nowait()
                        print(f"[{uri}] {error}")
                except Exception as e:
                    print(f"Error processing message queue: {e}")
                
                time.sleep(1)

        except KeyboardInterrupt:
            print("\nReceived keyboard interrupt")
        finally:
            self.stop_recording()

def main():
    parser = argparse.ArgumentParser(
        description="Record multiple RTSP streams with timestamp overlay and automatic reconnection."
    )
    parser.add_argument(
        'uris', nargs='*', metavar='RTSP_URI',
        help='RTSP stream URIs'
    )
    parser.add_argument(
        '-f', '--file', metavar='FILE',
        help='Text file containing RTSP URIs, one per line'
    )
    parser.add_argument(
        '-o', '--output', metavar='OUTPUT',
        help='Output directory for recordings'
    )
    args = parser.parse_args()

    # Collect URIs from arguments and file
    uris = args.uris.copy()
    if args.file:
        try:
            with open(args.file, 'r') as f:
                file_uris = [line.strip() for line in f if line.strip()]
                uris.extend(file_uris)
        except Exception as e:
            print(f"Error reading file {args.file}: {e}")
            sys.exit(1)

    if not uris:
        parser.error('No RTSP URIs provided. Use positional args or -f FILE.')

    # Start recording
    recorder = RTSPRecorder(output_dir=args.output)
    recorder.run(uris)

if __name__ == '__main__':
    main()
