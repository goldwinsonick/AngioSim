from __future__ import annotations
import time
import yaml
import numpy as np
from collections import deque
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QGroupBox, QLabel, QComboBox, QPushButton, QFileDialog,
    QStatusBar, QToolBar, QMessageBox, QSlider,
)

from core.camera_manager import CameraManager, RESOLUTION_PRESETS, scan_cameras
from core.image_processor import FluoroscopyImageProcessor
from core.stages import STAGE_REGISTRY
from ui.dual_view import DualView
from ui.pipeline_editor import PipelineEditor
from ui.stage_config_widget import StageConfigWidget

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
SESSION_CONFIG = CONFIG_DIR / "session.yaml"
DEFAULT_CONFIG = CONFIG_DIR / "default.yaml"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FluoroscopyTest — Image Processing Workbench")
        self.resize(1400, 800)

        self._processor = FluoroscopyImageProcessor()
        self._camera = CameraManager(self)
        self._last_frames: list[np.ndarray] = []
        self._last_seq: int = -1
        self._browse_path: str = ""
        self._out_timestamps: deque[float] = deque(maxlen=30)

        self._build_ui()
        self._connect_signals()
        self._refresh_cameras()
        self._load_config(SESSION_CONFIG if SESSION_CONFIG.exists() else DEFAULT_CONFIG)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        tb = QToolBar("Controls")
        tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        # ---- source type ----
        tb.addWidget(QLabel(" Source: "))
        self._src_combo = QComboBox()
        self._src_combo.addItems(["Camera", "Video", "Image"])
        self._src_combo.setFixedWidth(90)
        tb.addWidget(self._src_combo)

        # ---- camera controls (hidden for video/image) ----
        lbl_camera = QLabel("  Camera: ")
        self._act_lbl_camera = tb.addWidget(lbl_camera)
        self._cam_combo = QComboBox()
        self._cam_combo.setFixedWidth(120)
        self._act_cam_combo = tb.addWidget(self._cam_combo)

        self._btn_rescan = QPushButton("Rescan")
        self._btn_rescan.setFixedWidth(60)
        self._act_rescan = tb.addWidget(self._btn_rescan)

        lbl_res = QLabel("  Resolution: ")
        self._act_lbl_res = tb.addWidget(lbl_res)
        self._res_combo = QComboBox()
        self._res_combo.addItems(list(RESOLUTION_PRESETS.keys()))
        self._res_combo.setFixedWidth(130)
        self._act_res_combo = tb.addWidget(self._res_combo)

        # ---- file browse (hidden for camera) ----
        self._btn_browse = QPushButton("Browse…")
        self._btn_browse.setFixedWidth(70)
        self._act_browse = tb.addWidget(self._btn_browse)
        self._act_browse.setVisible(False)

        tb.addSeparator()

        # ---- start / pause / stop ----
        self._btn_action = QPushButton("Start")
        self._btn_action.setFixedWidth(70)
        tb.addWidget(self._btn_action)

        tb.addSeparator()

        # ---- video trackbar (hidden for camera/image) ----
        self._video_slider = QSlider(Qt.Orientation.Horizontal)
        self._video_slider.setMinimumWidth(220)
        self._video_slider.setRange(0, 1)
        self._act_video_slider = tb.addWidget(self._video_slider)
        self._act_video_slider.setVisible(False)

        self._lbl_video_pos = QLabel("0 / 0")
        self._lbl_video_pos.setFixedWidth(90)
        self._act_video_pos = tb.addWidget(self._lbl_video_pos)
        self._act_video_pos.setVisible(False)

        tb.addSeparator()

        # ---- stats (never embedded in image) ----
        self._lbl_src_fps = QLabel("Src: --")     # camera/video capture rate
        self._lbl_src_fps.setFixedWidth(75)
        tb.addWidget(self._lbl_src_fps)

        self._lbl_out_fps = QLabel("Out: --")     # actual processed/displayed rate
        self._lbl_out_fps.setFixedWidth(75)
        tb.addWidget(self._lbl_out_fps)

        self._lbl_res_info = QLabel("--x--")
        self._lbl_res_info.setFixedWidth(90)
        tb.addWidget(self._lbl_res_info)

        self._lbl_proc = QLabel("Proc: -- ms")
        self._lbl_proc.setFixedWidth(100)
        tb.addWidget(self._lbl_proc)

        # ---- central area ----
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        self._dual_view = DualView()
        splitter.addWidget(self._dual_view)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(6)

        pipe_box = QGroupBox("Pipeline")
        pipe_box_layout = QVBoxLayout(pipe_box)
        pipe_box_layout.setContentsMargins(4, 4, 4, 4)
        self._pipeline_editor = PipelineEditor(self._processor.pipeline)
        pipe_box_layout.addWidget(self._pipeline_editor)
        right_layout.addWidget(pipe_box, stretch=1)

        config_box = QGroupBox("Stage Config")
        config_box_layout = QVBoxLayout(config_box)
        config_box_layout.setContentsMargins(4, 4, 4, 4)
        self._stage_config = StageConfigWidget()
        config_box_layout.addWidget(self._stage_config)
        right_layout.addWidget(config_box, stretch=2)

        btn_row = QHBoxLayout()
        self._btn_save_cfg = QPushButton("Save Config")
        self._btn_load_cfg = QPushButton("Load Config")
        btn_row.addWidget(self._btn_save_cfg)
        btn_row.addWidget(self._btn_load_cfg)
        right_layout.addLayout(btn_row)

        splitter.addWidget(right_panel)
        splitter.setSizes([900, 450])

        self.setStatusBar(QStatusBar())

        # Pull timer: fires at ~30fps, pulls latest frame from the camera thread.
        # This decouples display rate from camera rate and prevents signal queue flooding.
        self._display_timer = QTimer(self)
        self._display_timer.setInterval(16)

    # ------------------------------------------------------------------
    # Signal Wiring
    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self._src_combo.currentTextChanged.connect(self._on_source_type_changed)
        self._btn_rescan.clicked.connect(self._refresh_cameras)
        self._btn_browse.clicked.connect(self._browse_file)
        self._btn_action.clicked.connect(self._on_action_button)

        self._camera.thread.fps_updated.connect(self._on_fps)
        self._camera.thread.error_occurred.connect(self._on_camera_error)
        self._camera.thread.position_updated.connect(self._on_video_position)

        self._display_timer.timeout.connect(self._pull_and_process)

        self._video_slider.sliderMoved.connect(self._on_video_seek)

        self._pipeline_editor.pipeline_changed.connect(self._on_pipeline_changed)
        self._pipeline_editor.stage_selected.connect(self._on_stage_selected)

        self._stage_config.param_changed.connect(self._reprocess_last)

        self._dual_view.left_stage_changed.connect(lambda _: self._reprocess_last())
        self._dual_view.right_stage_changed.connect(lambda _: self._reprocess_last())

        self._btn_save_cfg.clicked.connect(self._save_config_dialog)
        self._btn_load_cfg.clicked.connect(self._load_config_dialog)

    # ------------------------------------------------------------------
    # Camera / Source
    # ------------------------------------------------------------------
    def _refresh_cameras(self) -> None:
        indices = scan_cameras()
        self._cam_combo.clear()
        if indices:
            for i in indices:
                self._cam_combo.addItem(f"Camera {i}", userData=i)
        else:
            self._cam_combo.addItem("No cameras found", userData=-1)

    def _on_source_type_changed(self, src_type: str) -> None:
        is_file = src_type in ("Video", "Image")
        is_video = src_type == "Video"

        self._act_lbl_camera.setVisible(not is_file)
        self._act_cam_combo.setVisible(not is_file)
        self._act_rescan.setVisible(not is_file)
        self._act_lbl_res.setVisible(not is_file)
        self._act_res_combo.setVisible(not is_file)
        self._act_browse.setVisible(is_file)
        self._act_video_slider.setVisible(is_video)
        self._act_video_pos.setVisible(is_video)

    def _browse_file(self) -> None:
        src = self._src_combo.currentText()
        if src == "Video":
            path, _ = QFileDialog.getOpenFileName(
                self, "Open Video", "", "Video Files (*.mp4 *.avi *.mkv *.mov)"
            )
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.tiff)"
            )
        if path:
            self._browse_path = path
            name = Path(path).name
            self._btn_browse.setText(name[:18] + "…" if len(name) > 18 else name)

    # ------------------------------------------------------------------
    # Start / Pause / Resume / Stop
    # ------------------------------------------------------------------
    def _on_action_button(self) -> None:
        src_type = self._src_combo.currentText()
        thread = self._camera.thread

        if not self._camera.is_running():
            self._start_stream()
            return

        if src_type == "Video":
            if thread.is_paused():
                thread.resume()
                self._btn_action.setText("Pause")
            else:
                thread.pause()
                self._btn_action.setText("Resume")
        else:
            self._stop_stream()

    def _start_stream(self) -> None:
        src_type = self._src_combo.currentText()

        if src_type == "Camera":
            source = self._cam_combo.currentData()
            if source is None or source < 0:
                QMessageBox.warning(self, "No Camera", "No camera available.")
                return
            self._camera.start("camera", source, self._res_combo.currentText())
            self._btn_action.setText("Stop")

        elif src_type == "Video":
            if not self._browse_path:
                QMessageBox.warning(self, "No File", "Choose a video file first.")
                return
            self._camera.start("video", self._browse_path, "")
            self._btn_action.setText("Pause")

        else:  # Image
            if not self._browse_path:
                QMessageBox.warning(self, "No File", "Choose an image file first.")
                return
            self._camera.start("image", self._browse_path, "")
            self._btn_action.setText("Stop")

        self._display_timer.start()

    def _stop_stream(self) -> None:
        self._display_timer.stop()
        self._camera.stop()
        self._btn_action.setText("Start")
        self._dual_view.clear()
        self._lbl_src_fps.setText("Src: --")
        self._lbl_out_fps.setText("Out: --")
        self._out_timestamps.clear()
        self._last_seq = -1

    # ------------------------------------------------------------------
    # Frame Processing (pull-based — no signal flooding)
    # ------------------------------------------------------------------
    def _pull_and_process(self) -> None:
        result = self._camera.thread.get_latest_frame()
        if result is None:
            return
        frame, seq = result
        if seq == self._last_seq:
            return   # same frame as last display tick, skip reprocess
        self._last_seq = seq
        self._on_frame(frame)

    def _on_frame(self, frame: np.ndarray) -> None:
        stage_frames, elapsed_ms, timings = self._processor.process(frame)
        self._last_frames = stage_frames
        h, w = frame.shape[:2]
        self._lbl_res_info.setText(f"{w}x{h}")
        self._lbl_proc.setText(f"Proc: {elapsed_ms:.1f}ms")
        self._dual_view.update_frames(stage_frames)
        self._pipeline_editor.update_timings(timings)

        now = time.monotonic()
        self._out_timestamps.append(now)
        if len(self._out_timestamps) >= 2:
            span = self._out_timestamps[-1] - self._out_timestamps[0]
            out_fps = (len(self._out_timestamps) - 1) / span if span > 0 else 0.0
            self._lbl_out_fps.setText(f"Out: {out_fps:.1f}")

    def _reprocess_last(self) -> None:
        if not self._last_frames:
            return
        raw = self._last_frames[0]
        stage_frames, elapsed_ms, timings = self._processor.process(raw)
        self._last_frames = stage_frames
        self._lbl_proc.setText(f"Proc: {elapsed_ms:.1f}ms")
        self._dual_view.update_frames(stage_frames)
        self._pipeline_editor.update_timings(timings)

    @pyqtSlot(float)
    def _on_fps(self, fps: float) -> None:
        self._lbl_src_fps.setText(f"Src: {fps:.1f}")

    @pyqtSlot(str)
    def _on_camera_error(self, msg: str) -> None:
        self._display_timer.stop()
        self._btn_action.setText("Start")
        self.statusBar().showMessage(f"Camera error: {msg}", 5000)

    # ------------------------------------------------------------------
    # Video trackbar
    # ------------------------------------------------------------------
    @pyqtSlot(int, int)
    def _on_video_position(self, current: int, total: int) -> None:
        self._video_slider.blockSignals(True)
        self._video_slider.setRange(0, total)
        self._video_slider.setValue(current)
        self._video_slider.blockSignals(False)
        self._lbl_video_pos.setText(f"{current} / {total}")

    def _on_video_seek(self, position: int) -> None:
        self._camera.thread.seek(position)

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------
    def _on_pipeline_changed(self) -> None:
        names = self._pipeline_editor.stage_names_for_display()
        self._dual_view.populate_stages(names)
        self._reprocess_last()

    def _on_stage_selected(self, row: int) -> None:
        stages = self._processor.pipeline.stages
        if 0 <= row < len(stages):
            self._stage_config.load_stage(stages[row])
        else:
            self._stage_config.load_stage(None)

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------
    def _build_config(self) -> dict:
        src_type = self._src_combo.currentText().lower()
        source = self._cam_combo.currentData() or 0 if src_type == "camera" else self._browse_path
        return {
            "camera": {
                "source_type": src_type,
                "source": source,
                "resolution": self._res_combo.currentText(),
            },
            "ui": {
                "left_stage_index":  self._dual_view.left_index(),
                "right_stage_index": self._dual_view.right_index(),
            },
            "pipeline": self._processor.pipeline.to_config(),
        }

    def _apply_config(self, cfg: dict) -> None:
        cam_cfg = cfg.get("camera", {})
        src_type = cam_cfg.get("source_type", "camera")
        self._src_combo.setCurrentIndex({"camera": 0, "video": 1, "image": 2}.get(src_type, 0))

        source = cam_cfg.get("source", 0)
        if src_type == "camera":
            for i in range(self._cam_combo.count()):
                if self._cam_combo.itemData(i) == int(source):
                    self._cam_combo.setCurrentIndex(i)
                    break
        else:
            self._browse_path = str(source) if source else ""
            if self._browse_path:
                name = Path(self._browse_path).name
                self._btn_browse.setText(name[:18] + "…" if len(name) > 18 else name)

        res = cam_cfg.get("resolution", list(RESOLUTION_PRESETS.keys())[0])
        idx = self._res_combo.findText(res)
        if idx >= 0:
            self._res_combo.setCurrentIndex(idx)

        self._processor.pipeline.from_config(cfg.get("pipeline", []), STAGE_REGISTRY)
        self._pipeline_editor.refresh()

        names = self._pipeline_editor.stage_names_for_display()
        self._dual_view.populate_stages(names)

        ui_cfg = cfg.get("ui", {})
        self._dual_view.set_left_index(ui_cfg.get("left_stage_index", 0))
        self._dual_view.set_right_index(ui_cfg.get("right_stage_index", max(0, len(names) - 1)))

    def _load_config(self, path: Path) -> None:
        try:
            with open(path) as f:
                cfg = yaml.safe_load(f) or {}
            self._apply_config(cfg)
        except Exception as e:
            self.statusBar().showMessage(f"Config load error: {e}", 5000)

    def _save_config(self, path: Path) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w") as f:
                yaml.dump(self._build_config(), f, default_flow_style=False)
        except Exception as e:
            self.statusBar().showMessage(f"Config save error: {e}", 5000)

    def _save_config_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Config", str(CONFIG_DIR), "YAML (*.yaml *.yml)"
        )
        if path:
            self._save_config(Path(path))
            self.statusBar().showMessage(f"Saved: {path}", 3000)

    def _load_config_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Config", str(CONFIG_DIR), "YAML (*.yaml *.yml)"
        )
        if path:
            self._load_config(Path(path))

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        self._display_timer.stop()
        self._camera.stop()
        self._save_config(SESSION_CONFIG)
        super().closeEvent(event)
