import sys
import os

# Ensure imports resolve from project root
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow


def _apply_dark_palette(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    dark = QColor(30, 30, 30)
    mid = QColor(50, 50, 50)
    light = QColor(70, 70, 70)
    text = QColor(220, 220, 220)
    accent = QColor(0, 120, 215)

    palette.setColor(QPalette.ColorRole.Window, dark)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, mid)
    palette.setColor(QPalette.ColorRole.AlternateBase, light)
    palette.setColor(QPalette.ColorRole.ToolTipBase, mid)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, mid)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Highlight, accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    app.setPalette(palette)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("FluoroscopyTest")
    _apply_dark_palette(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
