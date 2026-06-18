import cv2
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QSlider, QVBoxLayout,
)

from core.lens_calibration import LensCalibration


class LensCalibrationDialog(QDialog):
    """
    Interactive lens-undistortion tuner. Drag the radial-distortion sliders
    while watching a live cv2.undistort() preview of a representative frame
    (overlaid with a reference grid) until straight physical lines — frame
    edges, a ruler/tape measure, rows of screws — actually look straight.

    Saved once per camera/source via AnalyzerWindow; every subsequent video
    from that source loads and applies it automatically.
    """

    _SCALE = 1000

    def __init__(self, frame: np.ndarray, label: str,
                 existing: "LensCalibration | None" = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Lens Calibration — {label}")
        self.resize(920, 740)

        self._frame = frame
        h, w = frame.shape[:2]
        base = existing if existing is not None else LensCalibration(label=label, frame_width=w, frame_height=h)
        self._result = LensCalibration(
            label=label, frame_width=w, frame_height=h,
            k1=base.k1, k2=base.k2, p1=base.p1, p2=base.p2, focal_scale=base.focal_scale,
        )

        layout = QVBoxLayout(self)

        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumSize(640, 440)
        self._preview.setStyleSheet("background-color: #111;")
        layout.addWidget(self._preview, stretch=1)

        self._chk_grid = QCheckBox("Overlay reference grid")
        self._chk_grid.setChecked(True)
        self._chk_grid.toggled.connect(self._update_preview)
        layout.addWidget(self._chk_grid)

        self._k1_slider = self._add_param_row(layout, "k1  (barrel / pincushion)", -2.0, 2.0, base.k1)
        self._k2_slider = self._add_param_row(layout, "k2  (higher-order radial)", -2.0, 2.0, base.k2)
        self._focal_slider = self._add_param_row(layout, "focal scale", 0.3, 3.0, base.focal_scale)

        info = QLabel(
            "Tip: a negative k1 corrects barrel distortion (lines bowing outward, "
            "as seen on the top camera); positive k1 corrects pincushion distortion. "
            "This is saved once for this camera and reused for every video from it — "
            "you will not need to repeat it."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(info)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_preview()

    def _add_param_row(self, layout: QVBoxLayout, name: str,
                       lo: float, hi: float, default: float) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(lo * self._SCALE), int(hi * self._SCALE))
        slider.setValue(int(default * self._SCALE))
        lbl_name = QLabel(name)
        lbl_name.setFixedWidth(170)
        lbl_val = QLabel(f"{default:+.3f}")
        lbl_val.setFixedWidth(56)
        slider.valueChanged.connect(lambda v: self._on_param_changed(slider, lbl_val))
        row = QHBoxLayout()
        row.addWidget(lbl_name)
        row.addWidget(slider, stretch=1)
        row.addWidget(lbl_val)
        layout.addLayout(row)
        return slider

    def _on_param_changed(self, slider: QSlider, lbl_val: QLabel) -> None:
        lbl_val.setText(f"{slider.value() / self._SCALE:+.3f}")
        self._update_preview()

    def _update_preview(self) -> None:
        self._result.k1 = self._k1_slider.value() / self._SCALE
        self._result.k2 = self._k2_slider.value() / self._SCALE
        self._result.focal_scale = self._focal_slider.value() / self._SCALE

        undistorted = self._result.undistort_frame(self._frame)
        if self._chk_grid.isChecked():
            undistorted = self._draw_grid(undistorted)

        h, w = undistorted.shape[:2]
        rgb = cv2.cvtColor(undistorted, cv2.COLOR_BGR2RGB)
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            self._preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(pix)

    @staticmethod
    def _draw_grid(frame: np.ndarray, step: int = 80) -> np.ndarray:
        out = frame.copy()
        h, w = out.shape[:2]
        for x in range(0, w, step):
            cv2.line(out, (x, 0), (x, h), (0, 220, 0), 1, cv2.LINE_AA)
        for y in range(0, h, step):
            cv2.line(out, (0, y), (w, y), (0, 220, 0), 1, cv2.LINE_AA)
        return out

    def calibration(self) -> LensCalibration:
        return self._result
