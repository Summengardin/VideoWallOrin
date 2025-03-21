from PyQt6.QtWidgets import QMainWindow, QWidget
from PyQt6.QtCore import Qt

class GstWindow(QMainWindow):
    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance
        self.init_ui()

    def init_ui(self):
        self.video_widget = QWidget()
        self.setCentralWidget(self.video_widget)
        self.setWindowTitle('Vision Controller')
        self.resize(1920, 1080)

        self.video_widget.show()
        self.windowId = self.video_widget.winId()

        # Connect pipeline bus
        if self.app_instance.pipeline_manager:
            bus = self.app_instance.pipeline_manager.pipeline.get_bus()
            bus.add_signal_watch()
            bus.enable_sync_message_emission()
            bus.connect('sync-message::element', self.on_sync_message)

    def on_sync_message(self, bus, message):
        if message.get_structure().get_name() == 'prepare-window-handle':
            message.src.set_window_handle(self.windowId)

    def mouseDoubleClickEvent(self, event):
        self.toggle_fullscreen()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal() 
        else:
            self.showFullScreen()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()

    def closeEvent(self, event):
        self.app_instance.stop()
        event.accept()