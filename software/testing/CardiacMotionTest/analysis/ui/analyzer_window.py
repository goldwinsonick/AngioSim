import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QDoubleSpinBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSlider,
    QSplitter, QStatusBar, QVBoxLayout, QWidget,
)

from core.lens_calibration import LensCalibration
from core.marker_tracker import MarkerTracker
from core.setup import AnalysisSetup
from ui.lens_calibration_dialog import LensCalibrationDialog


# -----------------------------------------------------------------------
# Clickable video label — marker placement
# -----------------------------------------------------------------------

class VideoLabel(QLabel):
    clicked = pyqtSignal(int, int)                  # image-space x, y

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(480, 360)
        self.setStyleSheet("background-color: #111;")
        self.setText("Load a video to begin")
        self._img_w = 1
        self._img_h = 1
        self._click_mode = False

    def set_frame(self, frame: np.ndarray, fast: bool = False) -> None:
        h, w = frame.shape[:2]
        self._img_w = w
        self._img_h = h
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        transform = (Qt.TransformationMode.FastTransformation if fast
                     else Qt.TransformationMode.SmoothTransformation)
        pix = QPixmap.fromImage(img).scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            transform,
        )
        self.setPixmap(pix)

    def set_click_mode(self, enabled: bool) -> None:
        self._click_mode = enabled

    def _to_image_coords(self, pos) -> tuple[int, int] | None:
        pix = self.pixmap()
        if pix is None:
            return None
        x_off = (self.width() - pix.width()) // 2
        y_off = (self.height() - pix.height()) // 2
        px = pos.x() - x_off
        py = pos.y() - y_off
        sx = self._img_w / pix.width() if pix.width() > 0 else 1
        sy = self._img_h / pix.height() if pix.height() > 0 else 1
        ix = int(px * sx)
        iy = int(py * sy)
        ix = max(0, min(ix, self._img_w - 1))
        iy = max(0, min(iy, self._img_h - 1))
        return ix, iy

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self._click_mode:
            return
        pt = self._to_image_coords(event.position())
        if pt is not None:
            self.clicked.emit(*pt)


# -----------------------------------------------------------------------
# Main window
#
# Scope is deliberately narrow: undistort the footage (top camera only —
# the side/phone camera has negligible distortion and is loaded as-is),
# let the user mark each tracked point at its REST position, and persist
# that as a setup file. Tracking, px↔mm calibration, and displacement math
# all happen downstream in the comparison notebook.
# -----------------------------------------------------------------------

class AnalyzerWindow(QMainWindow):
    _CALIBRATION_DIR = Path(__file__).resolve().parent.parent / "calibration"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AngioSim — Motion Analyzer")
        self.resize(1280, 800)

        self._video_path: Path | None = None
        self._cap: cv2.VideoCapture | None = None
        self._total_frames = 0
        self._fps = 30.0
        self._frame_w = 1
        self._frame_h = 1

        # Markers double as the rest reference: rest_frame_index = frame
        # the user was on when the *last* marker was placed.
        self._marker_positions: list[tuple[int, int]] = []
        self._rest_frame_index: int | None = None
        self._adding_marker = False

        # Measurement tool state (separate from marker placement)
        self._measuring = False
        self._measure_points: list[tuple[int, int]] = []

        # Lens calibration is shared per camera/source ("top"/"side") — loaded
        # automatically from analysis/calibration/<label>_lens.json based on
        # the video's folder. The top camera needs it (significant barrel
        # distortion); the side/phone camera doesn't, so no "side_lens.json"
        # is ever created and frames simply pass through uncorrected.
        self._lens_calibration: LensCalibration | None = None

        self._playing = False
        self._play_timer = QTimer(self)
        self._play_timer.timeout.connect(self._play_tick)

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # ---- Toolbar: file / setup persistence ----
        toolbar = QHBoxLayout()
        btn_load = QPushButton("Load Video…")
        btn_load.clicked.connect(self._on_load_video)
        btn_save_setup = QPushButton("Save Setup")
        btn_save_setup.clicked.connect(self._on_save_setup)
        btn_load_setup = QPushButton("Load Setup")
        btn_load_setup.clicked.connect(lambda: self._on_load_setup(silent=False))

        for w in (btn_load, btn_save_setup, btn_load_setup):
            toolbar.addWidget(w)
        toolbar.addStretch()
        root.addLayout(toolbar)

        # ---- Calibration row: lens undistortion (shared per camera) ----
        calib_row = QHBoxLayout()
        self._btn_lens_calib = QPushButton("Lens Calibration…")
        self._btn_lens_calib.clicked.connect(self._on_lens_calibration)
        self._lbl_lens = QLabel("Lens: not calibrated")
        self._lbl_lens.setStyleSheet("color: #aaa; font-size: 11px;")

        self._sync_spin = QDoubleSpinBox()
        self._sync_spin.setRange(-3600.0, 3600.0)
        self._sync_spin.setSingleStep(0.1)
        self._sync_spin.setSuffix(" s sync offset")

        calib_row.addWidget(self._btn_lens_calib)
        calib_row.addWidget(self._lbl_lens)
        calib_row.addSpacing(16)
        calib_row.addWidget(self._sync_spin)
        calib_row.addStretch()
        root.addLayout(calib_row)

        # ---- Main splitter: video | markers ----
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, stretch=1)

        # Left: video frame + seek + nav
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._video_label = VideoLabel()
        self._video_label.clicked.connect(self._on_video_clicked)
        left_layout.addWidget(self._video_label, stretch=1)

        seek_row = QHBoxLayout()
        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.valueChanged.connect(
            lambda v: self._lbl_frame.setText(f"Frame: {v} / {self._total_frames - 1}")
        )
        self._seek_slider.sliderPressed.connect(self._stop_playback)
        self._seek_slider.sliderReleased.connect(
            lambda: self._show_frame(self._seek_slider.value())
        )
        self._lbl_frame = QLabel("Frame: 0 / 0")
        seek_row.addWidget(self._seek_slider)
        seek_row.addWidget(self._lbl_frame)
        left_layout.addLayout(seek_row)

        nav_row = QHBoxLayout()
        self._btn_play = QPushButton("▶  Play")
        self._btn_play.setEnabled(False)
        self._btn_play.setFixedWidth(80)
        self._btn_play.clicked.connect(self._on_play_pause)
        nav_row.addWidget(self._btn_play)
        for label, delta in [("◀◀ -10", -10), ("◀ -1", -1), ("+1 ▶", 1), ("+10 ▶▶", 10)]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, d=delta: self._step_frame(d))
            nav_row.addWidget(btn)
        nav_row.addStretch()
        left_layout.addLayout(nav_row)

        splitter.addWidget(left)

        # Right: marker placement
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)

        right_layout.addWidget(QLabel(
            "Markers — scrub to the REST frame, then click to place them:"
        ))

        self._btn_add_marker = QPushButton("+ Add Marker")
        self._btn_add_marker.clicked.connect(self._on_add_marker)
        self._btn_add_marker.setEnabled(False)
        btn_clear_markers = QPushButton("Clear All")
        btn_clear_markers.clicked.connect(self._on_clear_markers)
        m_row = QHBoxLayout()
        m_row.addWidget(self._btn_add_marker)
        m_row.addWidget(btn_clear_markers)
        right_layout.addLayout(m_row)

        btn_measure = QPushButton("Measure Distance…")
        btn_measure.clicked.connect(self._on_measure_distance)
        right_layout.addWidget(btn_measure)

        self._lbl_rest = QLabel("Rest frame: —")
        self._lbl_rest.setStyleSheet("color: #aaa; font-size: 11px;")
        right_layout.addWidget(self._lbl_rest)

        self._marker_list_widget = QWidget()
        self._marker_list_layout = QVBoxLayout(self._marker_list_widget)
        self._marker_list_layout.setSpacing(2)
        self._marker_list_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._marker_list_widget)
        right_layout.addWidget(scroll, stretch=1)

        splitter.addWidget(right)
        splitter.setSizes([900, 380])

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

    # ------------------------------------------------------------------
    # Video loading & seeking
    # ------------------------------------------------------------------

    def _on_load_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", "", "Video Files (*.mp4 *.avi *.mov *.mkv)"
        )
        if not path:
            return
        self._stop_playback()
        if self._cap:
            self._cap.release()
        self._cap = cv2.VideoCapture(path)
        if not self._cap.isOpened():
            QMessageBox.critical(self, "Error", f"Cannot open {path}")
            return
        self._video_path = Path(path)
        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._frame_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._frame_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._seek_slider.setRange(0, max(0, self._total_frames - 1))
        self._seek_slider.setValue(0)

        self._on_clear_markers()
        self._sync_spin.setValue(0.0)
        self._load_lens_calibration_for_video()

        self._show_frame(0)
        self._btn_add_marker.setEnabled(True)
        self._btn_play.setEnabled(True)
        self._status_bar.showMessage(
            f"Loaded: {self._video_path.name}  |  "
            f"{self._total_frames} frames @ {self._fps:.1f} fps  |  "
            f"{self._frame_w}×{self._frame_h}"
        )
        self._on_load_setup(silent=True)

    def _correct(self, frame: np.ndarray) -> np.ndarray:
        """Applies the active lens calibration to a raw frame, if any.

        This is the single point where lens correction happens — every frame
        that gets displayed, clicked on, or saved into the setup's reference
        passes through here first, so there is exactly one coordinate space
        throughout the app. For "side" videos no calibration file exists, so
        this is a no-op and the frame passes through untouched."""
        return (self._lens_calibration.undistort_frame(frame)
                if self._lens_calibration is not None else frame)

    def _show_frame(self, idx: int) -> None:
        """Seek to a specific frame index (random access — use for stepping/scrubbing)."""
        if self._cap is None:
            return
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = self._cap.read()
        if not ok:
            return
        frame = self._correct(frame)
        self._lbl_frame.setText(f"Frame: {idx} / {self._total_frames - 1}")
        self._display_frame(frame, fast=False)

    def _display_frame(self, frame: np.ndarray, fast: bool = False) -> None:
        """Draw placed-marker overlays on an already lens-corrected frame and push it to the view."""
        if self._marker_positions:
            frame = MarkerTracker.draw_markers(frame, self._marker_positions)
        self._video_label.set_frame(frame, fast=fast)

    def _on_play_pause(self) -> None:
        if self._playing:
            self._stop_playback()
        else:
            self._start_playback()

    def _start_playback(self) -> None:
        if self._cap is None:
            return
        self._playing = True
        self._btn_play.setText("⏸  Pause")
        interval_ms = max(10, int(1000 / self._fps))
        self._play_timer.start(interval_ms)

    def _stop_playback(self) -> None:
        self._playing = False
        self._play_timer.stop()
        self._btn_play.setText("▶  Play")

    def _play_tick(self) -> None:
        if self._cap is None:
            self._stop_playback()
            return
        ok, frame = self._cap.read()
        if not ok:
            self._stop_playback()
            return
        frame = self._correct(frame)
        idx = int(self._cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
        self._seek_slider.blockSignals(True)
        self._seek_slider.setValue(idx)
        self._seek_slider.blockSignals(False)
        self._lbl_frame.setText(f"Frame: {idx} / {self._total_frames - 1}")
        self._display_frame(frame, fast=True)

    def _step_frame(self, delta: int) -> None:
        self._stop_playback()
        new_val = max(0, min(self._seek_slider.value() + delta, self._total_frames - 1))
        self._seek_slider.blockSignals(True)
        self._seek_slider.setValue(new_val)
        self._seek_slider.blockSignals(False)
        self._show_frame(new_val)

    # ------------------------------------------------------------------
    # Marker management (placement frame doubles as the rest reference)
    # ------------------------------------------------------------------

    def _on_add_marker(self) -> None:
        self._adding_marker = True
        self._video_label.set_click_mode(True)
        self._status_bar.showMessage(
            f"Click on marker {len(self._marker_positions)} at the REST frame…"
        )

    def _on_clear_markers(self) -> None:
        self._marker_positions = []
        self._rest_frame_index = None
        self._lbl_rest.setText("Rest frame: —")
        self._update_marker_list()
        if self._cap is not None and self._seek_slider.value() == 0:
            self._show_frame(0)

    def _update_marker_list(self) -> None:
        while self._marker_list_layout.count() > 1:
            item = self._marker_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        colors = ["#00d4ff", "#ff9f00", "#ff5555", "#88ff00", "#cc88ff"]
        for i, (x, y) in enumerate(self._marker_positions):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            color = colors[i % len(colors)]
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 14px;")
            row_layout.addWidget(dot)
            row_layout.addWidget(QLabel(f"Marker {i}  ({x}, {y})"))
            row_layout.addStretch()
            btn_rm = QPushButton("×")
            btn_rm.setFixedWidth(24)
            btn_rm.clicked.connect(lambda _, idx=i: self._remove_marker(idx))
            row_layout.addWidget(btn_rm)
            self._marker_list_layout.insertWidget(
                self._marker_list_layout.count() - 1, row
            )

    def _remove_marker(self, idx: int) -> None:
        if idx < len(self._marker_positions):
            self._marker_positions.pop(idx)
            if not self._marker_positions:
                self._rest_frame_index = None
                self._lbl_rest.setText("Rest frame: —")
            self._update_marker_list()
            self._show_frame(self._seek_slider.value())

    def _on_video_clicked(self, x: int, y: int) -> None:
        if self._measuring:
            self._measure_points.append((x, y))
            if len(self._measure_points) == 1:
                self._status_bar.showMessage("Click the second point of the reference length…")
            else:
                self._finish_measurement()
            return
        if not self._adding_marker:
            return
        self._marker_positions.append((x, y))
        self._rest_frame_index = self._seek_slider.value()
        self._lbl_rest.setText(f"Rest frame: {self._rest_frame_index}")
        self._update_marker_list()
        n = len(self._marker_positions)
        self._status_bar.showMessage(
            f"Marker {n - 1} placed at ({x}, {y})  —  rest frame = {self._rest_frame_index}"
        )
        self._adding_marker = False
        self._video_label.set_click_mode(False)
        self._show_frame(self._seek_slider.value())

    # ------------------------------------------------------------------
    # Lens calibration — shared per camera/source, loaded automatically
    # ------------------------------------------------------------------

    def _load_lens_calibration_for_video(self) -> None:
        """
        Auto-loads <source>_lens.json (e.g. "top_lens.json") based on which
        data folder the video lives in, so lens correction is calibrated once
        per camera and silently reused for every video from that camera. The
        side/phone camera has negligible distortion, so no "side_lens.json"
        is ever created — those videos simply pass through uncorrected.
        """
        self._lens_calibration = None
        if self._video_path is not None:
            label = LensCalibration.source_label_for(self._video_path)
            path = LensCalibration.path_for(label, self._CALIBRATION_DIR)
            if path.exists():
                try:
                    calib = LensCalibration.load(path)
                    if calib.frame_width == self._frame_w and calib.frame_height == self._frame_h:
                        self._lens_calibration = calib
                    else:
                        self._status_bar.showMessage(
                            f"Lens calibration '{label}' was made at a different resolution "
                            f"({calib.frame_width}×{calib.frame_height}) — re-run Lens Calibration…", 8000
                        )
                except Exception:
                    pass
        self._update_lens_label()

    def _update_lens_label(self) -> None:
        if self._lens_calibration is None:
            self._lbl_lens.setText("Lens: not calibrated")
        else:
            c = self._lens_calibration
            self._lbl_lens.setText(f"Lens: {c.label}  (k1={c.k1:+.3f}, k2={c.k2:+.3f})")

    def _on_lens_calibration(self) -> None:
        if self._cap is None or self._video_path is None:
            QMessageBox.information(self, "Lens Calibration", "Load a video first.")
            return
        idx = self._seek_slider.value()
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = self._cap.read()
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        if not ok:
            QMessageBox.warning(self, "Lens Calibration", "Cannot read the current frame.")
            return

        label = LensCalibration.source_label_for(self._video_path)
        dialog = LensCalibrationDialog(frame, label, self._lens_calibration, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        calib = dialog.calibration()
        try:
            self._CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
            calib.save(LensCalibration.path_for(label, self._CALIBRATION_DIR))
        except Exception as e:
            QMessageBox.warning(self, "Lens Calibration", f"Cannot save calibration: {e}")
            return

        self._lens_calibration = calib
        self._update_lens_label()
        self._status_bar.showMessage(
            f"Lens calibration saved for '{label}' — every {label} video will use it automatically.", 6000
        )
        self._show_frame(self._seek_slider.value())

    # ------------------------------------------------------------------
    # Setup persistence
    # ------------------------------------------------------------------

    def _on_save_setup(self) -> None:
        if self._video_path is None or self._rest_frame_index is None:
            QMessageBox.information(self, "Save Setup", "Place at least one marker first.")
            return
        setup = AnalysisSetup(
            video_name=self._video_path.name,
            frame_width=self._frame_w,
            frame_height=self._frame_h,
            markers=[[x, y] for x, y in self._marker_positions],
            rest_frame_index=self._rest_frame_index,
            sync_offset_s=self._sync_spin.value(),
        )
        path = AnalysisSetup.setup_path_for(self._video_path)
        try:
            setup.save(path)
        except Exception as e:
            QMessageBox.warning(self, "Save Setup", f"Cannot save setup: {e}")
            return
        self._status_bar.showMessage(f"Setup saved: {path.name}", 4000)

    def _on_load_setup(self, silent: bool = False) -> None:
        if self._video_path is None:
            return
        path = AnalysisSetup.setup_path_for(self._video_path)
        if not path.exists():
            if not silent:
                QMessageBox.information(self, "Load Setup", "No setup file found for this video.")
            return
        try:
            setup = AnalysisSetup.load(path)
        except Exception as e:
            if not silent:
                QMessageBox.warning(self, "Load Setup", f"Cannot load setup: {e}")
            return

        self._marker_positions = [(x, y) for x, y in setup.markers]
        self._rest_frame_index = setup.rest_frame_index
        self._lbl_rest.setText(
            f"Rest frame: {self._rest_frame_index}" if self._rest_frame_index is not None else "Rest frame: —"
        )
        self._sync_spin.setValue(setup.sync_offset_s)

        self._update_marker_list()
        self._show_frame(self._seek_slider.value())
        self._status_bar.showMessage(f"Setup loaded: {path.name}", 4000)

    def _on_measure_distance(self) -> None:
        if self._cap is None:
            QMessageBox.information(self, "Measure Distance", "Load a video first.")
            return
        self._measuring = True
        self._measure_points = []
        self._video_label.set_click_mode(True)
        self._status_bar.showMessage("Click the first point of a known reference length…")

    def _finish_measurement(self) -> None:
        (x1, y1), (x2, y2) = self._measure_points
        px_dist = math.hypot(x2 - x1, y2 - y1)
        self._measuring = False
        self._video_label.set_click_mode(False)
        self._measure_points = []

        mm, ok = QInputDialog.getDouble(
            self, "Measure Distance", "Real-world length of that segment (mm):",
            value=10.0, min=0.01, decimals=2,
        )
        if not ok or mm <= 0:
            self._status_bar.showMessage("Measurement cancelled.")
            return

        px_per_mm = px_dist / mm
        mm_per_px = mm / px_dist
        QMessageBox.information(
            self, "Measurement result",
            f"Pixel distance: {px_dist:.2f} px\n"
            f"Real length: {mm:.2f} mm\n\n"
            f"Scale: {px_per_mm:.4f} px/mm   ({mm_per_px:.4f} mm/px)"
        )
        self._status_bar.showMessage(f"Scale: {px_per_mm:.4f} px/mm")

    def closeEvent(self, event) -> None:
        self._stop_playback()
        if self._cap:
            self._cap.release()
        event.accept()


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = AnalyzerWindow()
    window.show()
    sys.exit(app.exec())
