from __future__ import annotations
import numpy as np
import cv2
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QComboBox, QSizePolicy,
)


def _ndarray_to_pixmap(frame: np.ndarray) -> QPixmap:
    if frame.ndim == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
    elif frame.shape[2] == 4:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
    else:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = frame.shape
    img = QImage(frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(img)


class ImagePanel(QWidget):
    """One image panel with a stage-selector dropdown above it."""

    stage_changed = pyqtSignal(int)  # emits panel-local stage index

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        self._label_text = label

        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(self.stage_changed)

        self._image_label = QLabel("No signal")
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._image_label.setMinimumSize(320, 240)
        self._image_label.setStyleSheet("background: #111; color: #555;")

        title = QLabel(label)
        title.setStyleSheet("font-weight: bold; color: #aaa; font-size: 11px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addWidget(title)
        layout.addWidget(self._combo)
        layout.addWidget(self._image_label, stretch=1)

    def populate_stages(self, stage_names: list[str]) -> None:
        current = self._combo.currentIndex()
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItems(stage_names)
        if 0 <= current < self._combo.count():
            self._combo.setCurrentIndex(current)
        else:
            self._combo.setCurrentIndex(self._combo.count() - 1)
        self._combo.blockSignals(False)

    def current_index(self) -> int:
        return self._combo.currentIndex()

    def set_index(self, index: int) -> None:
        if 0 <= index < self._combo.count():
            self._combo.setCurrentIndex(index)

    def show_frame(self, frame: np.ndarray) -> None:
        available = self._image_label.size()
        tw, th = available.width(), available.height()
        if tw <= 0 or th <= 0:
            return
        fh, fw = frame.shape[:2]
        scale = min(tw / fw, th / fh)
        new_w = max(1, int(fw * scale))
        new_h = max(1, int(fh * scale))
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        self._image_label.setPixmap(_ndarray_to_pixmap(resized))

    def clear(self) -> None:
        self._image_label.clear()
        self._image_label.setText("No signal")


class DualView(QWidget):
    """Side-by-side comparison of two pipeline stage outputs."""

    left_stage_changed = pyqtSignal(int)
    right_stage_changed = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._left = ImagePanel("Left")
        self._right = ImagePanel("Right")

        self._left.stage_changed.connect(self.left_stage_changed)
        self._right.stage_changed.connect(self.right_stage_changed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._left)
        layout.addWidget(self._right)

    def populate_stages(self, stage_names: list[str]) -> None:
        self._left.populate_stages(stage_names)
        self._right.populate_stages(stage_names)

    def left_index(self) -> int:
        return self._left.current_index()

    def right_index(self) -> int:
        return self._right.current_index()

    def set_left_index(self, index: int) -> None:
        self._left.set_index(index)

    def set_right_index(self, index: int) -> None:
        self._right.set_index(index)

    def update_frames(self, stage_frames: list[np.ndarray]) -> None:
        li = self._left.current_index()
        ri = self._right.current_index()
        if stage_frames and 0 <= li < len(stage_frames):
            self._left.show_frame(stage_frames[li])
        if stage_frames and 0 <= ri < len(stage_frames):
            self._right.show_frame(stage_frames[ri])

    def clear(self) -> None:
        self._left.clear()
        self._right.clear()
