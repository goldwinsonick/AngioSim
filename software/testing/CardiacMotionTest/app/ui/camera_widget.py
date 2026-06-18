import enum

import cv2
import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PyQt6.QtWidgets import QLabel


class InteractionMode(enum.Enum):
    NONE = 0
    DRAW_ROI = 1
    SET_LINE_P1 = 2
    SET_LINE_P2 = 3
    SET_CALIB_P1 = 4
    SET_CALIB_P2 = 5


class CameraWidget(QLabel):
    """
    Displays the live camera feed and handles mouse interaction for
    ROI drawing, measurement line placement, and calibration line.
    """

    roi_set = pyqtSignal(tuple)           # (x, y, w, h) in image coords
    line_set = pyqtSignal(tuple, tuple)   # (p1_x, p1_y), (p2_x, p2_y)
    calib_line_set = pyqtSignal(tuple, tuple)  # same format as line_set

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(480, 360)
        self.setStyleSheet("background-color: #111;")
        self.setText("No camera feed")

        self._mode = InteractionMode.NONE
        self._drag_start: QPoint | None = None
        self._drag_current: QPoint | None = None
        self._line_p1: QPoint | None = None

        # Current displayed pixmap dimensions for coordinate mapping
        self._img_w = 1
        self._img_h = 1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_frame(self, frame: np.ndarray) -> None:
        h, w = frame.shape[:2]
        self._img_w = w
        self._img_h = h
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        # FastTransformation for live preview — SmoothTransformation is too slow
        pix = QPixmap.fromImage(img).scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.setPixmap(pix)

    def begin_roi_draw(self) -> None:
        self._mode = InteractionMode.DRAW_ROI
        self.setCursor(Qt.CursorShape.CrossCursor)

    def begin_line_set(self) -> None:
        self._mode = InteractionMode.SET_LINE_P1
        self._line_p1 = None
        self.setCursor(Qt.CursorShape.CrossCursor)

    def begin_calib_line_set(self) -> None:
        self._mode = InteractionMode.SET_CALIB_P1
        self._line_p1 = None
        self.setCursor(Qt.CursorShape.CrossCursor)

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()

        if self._mode == InteractionMode.DRAW_ROI:
            self._drag_start = pos
            self._drag_current = pos

        elif self._mode == InteractionMode.SET_LINE_P1:
            self._line_p1 = pos
            self._mode = InteractionMode.SET_LINE_P2

        elif self._mode == InteractionMode.SET_LINE_P2:
            p1 = self._image_coords(self._line_p1)
            p2 = self._image_coords(pos)
            self.line_set.emit(p1, p2)
            self._mode = InteractionMode.NONE
            self.setCursor(Qt.CursorShape.ArrowCursor)

        elif self._mode == InteractionMode.SET_CALIB_P1:
            self._line_p1 = pos
            self._mode = InteractionMode.SET_CALIB_P2

        elif self._mode == InteractionMode.SET_CALIB_P2:
            p1 = self._image_coords(self._line_p1)
            p2 = self._image_coords(pos)
            self.calib_line_set.emit(p1, p2)
            self._mode = InteractionMode.NONE
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseMoveEvent(self, event) -> None:
        if self._mode == InteractionMode.DRAW_ROI and self._drag_start:
            self._drag_current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._mode == InteractionMode.DRAW_ROI and self._drag_start:
            p1 = self._image_coords(self._drag_start)
            p2 = self._image_coords(event.position().toPoint())
            x = min(p1[0], p2[0])
            y = min(p1[1], p2[1])
            w = abs(p2[0] - p1[0])
            h = abs(p2[1] - p1[1])
            if w > 5 and h > 5:
                self.roi_set.emit((x, y, w, h))
            self._drag_start = None
            self._drag_current = None
            self._mode = InteractionMode.NONE
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._mode == InteractionMode.DRAW_ROI and self._drag_start and self._drag_current:
            painter = QPainter(self)
            pen = QPen(QColor(0, 200, 255), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            x = min(self._drag_start.x(), self._drag_current.x())
            y = min(self._drag_start.y(), self._drag_current.y())
            w = abs(self._drag_current.x() - self._drag_start.x())
            h = abs(self._drag_current.y() - self._drag_start.y())
            painter.drawRect(x, y, w, h)
            painter.end()

    # ------------------------------------------------------------------
    # Coordinate mapping: widget pixel → image pixel
    # ------------------------------------------------------------------

    def _image_coords(self, widget_pos: QPoint) -> tuple[int, int]:
        pix = self.pixmap()
        if pix is None:
            return (widget_pos.x(), widget_pos.y())

        pw = pix.width()
        ph = pix.height()
        ww = self.width()
        wh = self.height()

        # Pixmap is centred inside the label
        x_offset = (ww - pw) // 2
        y_offset = (wh - ph) // 2

        x_in_pix = widget_pos.x() - x_offset
        y_in_pix = widget_pos.y() - y_offset

        # Scale from pixmap coords to image coords
        scale_x = self._img_w / pw if pw > 0 else 1
        scale_y = self._img_h / ph if ph > 0 else 1

        img_x = int(x_in_pix * scale_x)
        img_y = int(y_in_pix * scale_y)
        img_x = max(0, min(img_x, self._img_w - 1))
        img_y = max(0, min(img_y, self._img_h - 1))
        return (img_x, img_y)
