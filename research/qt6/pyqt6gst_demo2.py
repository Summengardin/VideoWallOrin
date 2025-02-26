import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GstVideo, GLib

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import Qt

class GstreamerPlayer(QMainWindow):
    def __init__(self, uri):
        super().__init__()
        self.uri = uri
        self.init_ui()
        self.init_gst()
        self.is_fullscreen = False

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)
        self.video_widget = QWidget()
        layout.addWidget(self.video_widget)
        btn_fullscreen = QPushButton('Toggle Fullscreen (F11)')
        btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        layout.addWidget(btn_fullscreen)
        self.setWindowTitle('RTSP Player')
        self.setGeometry(100, 100, 800, 600)

    def init_gst(self):
        Gst.init(None)
        self.pipeline = Gst.Pipeline.new("pipeline")

        # Create elements based on your working pipeline
        src = Gst.ElementFactory.make("uridecodebin")
        src.set_property("uri", self.uri)
        src.set_property("caps", Gst.Caps.from_string(
            "video/x-raw(memory:NVMM), width=1920, height=1080, format=NV12"))
        
        sink = Gst.ElementFactory.make("nv3dsink")
        sink.set_property("sync", False)

        # Add elements to pipeline
        self.pipeline.add(src)
        self.pipeline.add(sink)

        # Link elements (using pad-added signal due to uridecodebin)
        src.connect("pad-added", self.on_pad_added, sink)

        self.video_widget.show()
        self.windowId = self.video_widget.winId()

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::error', self.on_error)
        bus.enable_sync_message_emission()
        bus.connect('sync-message::element', self.on_sync_message)

        self.pipeline.set_state(Gst.State.PLAYING)

    def on_pad_added(self, element, pad, sink):
        pad.link(sink.get_static_pad("sink"))

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
    uri = "rtsp://root:root@10.1.3.81/axis-media/media.amp?streamprofile=stream-1"
    app = QApplication(sys.argv)
    player = GstreamerPlayer(uri)
    player.show()

    loop = GLib.MainLoop()
    import threading
    thread = threading.Thread(target=loop.run)
    thread.daemon = True
    thread.start()

    sys.exit(app.exec())