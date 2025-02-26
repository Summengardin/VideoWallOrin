from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import Qt
import sys

class FullscreenWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.is_fullscreen = False
        self.is_maximized = False

    def init_ui(self):
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create buttons
        btn_fullscreen = QPushButton('Toggle Fullscreen (F11)')
        btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        
        btn_maximized = QPushButton('Toggle Maximized (F10)')
        btn_maximized.clicked.connect(self.toggle_maximized)
        
        btn_normal = QPushButton('Normal Size (ESC)')
        btn_normal.clicked.connect(self.normal_size)

        # Add buttons to layout
        layout.addWidget(btn_fullscreen)
        layout.addWidget(btn_maximized)
        layout.addWidget(btn_normal)

        # Set window properties
        self.setWindowTitle('Fullscreen Test')
        self.setGeometry(100, 100, 400, 300)

    def toggle_fullscreen(self):
        if not self.is_fullscreen:
            self.showFullScreen()
            self.is_fullscreen = True
        else:
            self.normal_size()

    def toggle_maximized(self):
        if not self.is_maximized:
            self.showMaximized()
            self.is_maximized = True
        else:
            self.normal_size()

    def normal_size(self):
        self.showNormal()
        self.is_fullscreen = False
        self.is_maximized = False

    def keyPressEvent(self, event):
        # Handle keyboard shortcuts
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
        elif event.key() == Qt.Key.Key_F10:
            self.toggle_maximized()
        elif event.key() == Qt.Key.Key_Escape:
            self.normal_size()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = FullscreenWindow()
    window.show()
    sys.exit(app.exec())