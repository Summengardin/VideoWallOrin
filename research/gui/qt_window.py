from PyQt6.QtWidgets import QMainWindow, QApplication
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtCore import Qt
import sys

from VisionController.libs.gst.pipeline_manager import PipelineManager

class GstWindow(QMainWindow):
    def __init__(self, config=None):
        super().__init__()
        self.setWindowTitle("GStreamer Pipeline")
        self.resize(1920, 1080)
        
        # Initialize pipeline with config
        self.config = config or {}
        self.pipeline_manager = None
        
        QShortcut(QKeySequence("F11"), self, activated=self.toggleFullscreen)

    def mouseDoubleClickEvent(self, event):
        self.toggleFullscreen()

    def toggleFullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()

    def get_pipeline(self):
        if not self.pipeline_manager:
            self.pipeline_manager = PipelineManager(self.config)
        return self.pipeline_manager

    def closeEvent(self, event):
        if self.pipeline_manager:
            self.pipeline_manager.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = GstWindow()
    window.show()
    window.get_pipeline().start()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()