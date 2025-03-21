import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GstVideo, GLib

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import Qt

class GstreamerPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_gst()
        self.is_fullscreen = False

    def init_ui(self):
        # Create central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)

        # Create video widget
        self.video_widget = QWidget()
        layout.addWidget(self.video_widget)

        # Create fullscreen toggle button
        btn_fullscreen = QPushButton('Toggle Fullscreen (F11)')
        btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        layout.addWidget(btn_fullscreen)

        # Set window properties
        self.setWindowTitle('GStreamer Player')
        self.setGeometry(100, 100, 800, 600)

    def init_gst(self):
        # Initialize GStreamer
        Gst.init(None)

        # Create pipeline
        self.pipeline = Gst.Pipeline.new("pipeline")

        # Create elements
        # This example uses videotestsrc, but you can replace with your source
        src = Gst.ElementFactory.make("videotestsrc")
        convert = Gst.ElementFactory.make("videoconvert")
        sink = Gst.ElementFactory.make("xvimagesink")

        # Set properties
        if sink:
            sink.set_property("force-aspect-ratio", True)

        # Add elements to pipeline
        if all([src, convert, sink]):
            self.pipeline.add(src)
            self.pipeline.add(convert)
            self.pipeline.add(sink)
            src.link(convert)
            convert.link(sink)
        else:
            print("Failed to create elements")
            sys.exit(1)

        # Get X window ID after window is shown
        self.video_widget.show()
        self.windowId = self.video_widget.winId()

        # Set window handle on sink
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::error', self.on_error)
        bus.enable_sync_message_emission()
        bus.connect('sync-message::element', self.on_sync_message)

        # Start playing
        self.pipeline.set_state(Gst.State.PLAYING)

    def on_sync_message(self, bus, message):
        if message.get_structure().get_name() == 'prepare-window-handle':
            message.src.set_window_handle(self.windowId)

    def on_error(self, bus, message):
        err, debug = message.parse_error()
        print(f"Error: {err}, {debug}")

    def toggle_fullscreen(self):
        if not self.is_fullscreen:
            self.showFullScreen()
            self.is_fullscreen = True
        else:
            self.showNormal()
            self.is_fullscreen = False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Escape and self.is_fullscreen:
            self.showNormal()
            self.is_fullscreen = False

    def closeEvent(self, event):
        self.pipeline.set_state(Gst.State.NULL)
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    player = GstreamerPlayer()
    player.show()

    # Create GLib MainLoop for GStreamer message handling
    loop = GLib.MainLoop()
    
    # Run both Qt and GLib event loops
    import threading
    thread = threading.Thread(target=loop.run)
    thread.daemon = True
    thread.start()

    sys.exit(app.exec())