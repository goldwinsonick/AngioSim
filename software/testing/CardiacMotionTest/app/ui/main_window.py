import json
from datetime import datetime
from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QSplitter,
    QStatusBar, QTextEdit, QVBoxLayout, QWidget,
)

from core.camera import CameraThread
from core.serial_comm import SerialThread
from core.video_recorder import VideoRecorder
from core.session import Session
from ui.camera_widget import CameraWidget
from ui.pwm_panel import PwmPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AngioSim — Recording")
        self.resize(1280, 760)

        self._video_recorder = VideoRecorder()
        self._session_folder: Path | None = None
        self._frame_w = 1280
        self._frame_h = 720
        self._actual_fps = 30.0

        self._camera_thread: CameraThread | None = None
        self._serial_thread = SerialThread()

        self._setup_ui()
        self._connect_signals()
        self._load_settings()

        self._ping_timer = QTimer(self)
        self._ping_timer.setInterval(5000)
        self._ping_timer.timeout.connect(self._serial_thread.ping)

        self._restart_camera_thread()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # ---- Left: camera + record button ---------------------------
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        self._camera_widget = CameraWidget()
        left_layout.addWidget(self._camera_widget, stretch=1)

        # Record row
        rec_row = QHBoxLayout()
        self._btn_record = QPushButton("● Start Recording")
        self._btn_record.setCheckable(True)
        self._btn_record.setStyleSheet(
            "QPushButton:checked { background-color: #c0392b; color: white; font-weight: bold; }"
            "QPushButton:!checked { background-color: #444; color: white; }"
        )
        self._btn_record.toggled.connect(self._on_record_toggled)
        rec_row.addWidget(self._btn_record)

        self._lbl_frames = QLabel("Frames: 0")
        self._lbl_frames.setStyleSheet("color: #aaa; font-size: 11px;")
        self._lbl_fps = QLabel("FPS: —")
        self._lbl_fps.setStyleSheet("color: #aaa; font-size: 11px;")
        rec_row.addWidget(self._lbl_frames)
        rec_row.addWidget(self._lbl_fps)
        rec_row.addStretch()
        left_layout.addLayout(rec_row)

        splitter.addWidget(left)

        # ---- Right: controls ----------------------------------------
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # Session info
        right_layout.addWidget(self._sep("Session"))
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self._session_name = QLineEdit()
        self._session_name.setPlaceholderText("e.g. baseline_no_accumulator")
        name_row.addWidget(self._session_name)
        right_layout.addLayout(name_row)

        right_layout.addWidget(QLabel("Notes:"))
        self._session_notes = QTextEdit()
        self._session_notes.setFixedHeight(60)
        self._session_notes.setPlaceholderText("Optional notes about this run…")
        right_layout.addWidget(self._session_notes)

        # Camera selector
        right_layout.addWidget(self._sep("Camera"))
        right_layout.addLayout(self._build_camera_row())

        # Serial
        right_layout.addWidget(self._sep("ESP32 Serial"))
        right_layout.addLayout(self._build_serial_row())

        # PWM
        right_layout.addWidget(self._sep("PWM"))
        from PyQt6.QtWidgets import QScrollArea
        self._pwm_panel = PwmPanel()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._pwm_panel)
        right_layout.addWidget(scroll, stretch=1)

        splitter.addWidget(right)
        splitter.setSizes([820, 420])

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Camera starting…")

    # (width, height, label)
    RESOLUTIONS = [
        (640,  480,  "640×480"),
        (1280, 720,  "1280×720"),
        (1920, 1080, "1920×1080"),
    ]

    def _build_camera_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._camera_combo = QComboBox()
        self._camera_combo.setMinimumWidth(110)
        for i in range(6):
            self._camera_combo.addItem(f"Camera {i}", userData=i)

        self._res_combo = QComboBox()
        for w, h, label in self.RESOLUTIONS:
            self._res_combo.addItem(label, userData=(w, h))
        self._res_combo.setCurrentIndex(1)   # default 1280×720

        btn_scan = QPushButton("Scan")
        btn_scan.setFixedWidth(50)
        btn_scan.clicked.connect(self._refresh_cameras)

        btn_switch = QPushButton("Switch")
        btn_switch.setFixedWidth(55)
        btn_switch.clicked.connect(self._on_switch_camera)

        row.addWidget(QLabel("Cam:"))
        row.addWidget(self._camera_combo)
        row.addWidget(self._res_combo)
        row.addWidget(btn_scan)
        row.addWidget(btn_switch)
        row.addStretch()
        return row

    def _build_serial_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._port_combo = QComboBox()
        self._port_combo.setMinimumWidth(110)
        self._refresh_ports()

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setFixedWidth(60)
        btn_refresh.clicked.connect(self._refresh_ports)

        self._btn_connect = QPushButton("Connect")
        self._btn_connect.setCheckable(True)
        self._btn_connect.toggled.connect(self._on_connect_toggled)

        row.addWidget(QLabel("Port:"))
        row.addWidget(self._port_combo)
        row.addWidget(btn_refresh)
        row.addWidget(self._btn_connect)
        row.addStretch()
        return row

    @staticmethod
    def _sep(title: str = "") -> QLabel:
        lbl = QLabel(f"  {title}" if title else "")
        lbl.setFixedHeight(18)
        lbl.setStyleSheet(
            "background: #333; color: #aaa; font-size: 10px; "
            "border-radius: 2px; padding-left: 4px;"
        )
        return lbl

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self):
        # Camera thread signals are wired in _restart_camera_thread() because
        # the thread object is recreated on every switch/scan.

        self._serial_thread.ack_received.connect(
            lambda ack: self._status_bar.showMessage(f"ESP32: {ack}", 2000)
        )
        self._serial_thread.error_received.connect(
            lambda msg: self._status_bar.showMessage(f"Serial error: {msg}")
        )
        self._serial_thread.connected.connect(
            lambda: self._status_bar.showMessage("ESP32 connected")
        )
        self._serial_thread.disconnected.connect(self._on_serial_disconnected)

        self._pwm_panel.board_enable_changed.connect(self._serial_thread.set_board_enable)
        self._pwm_panel.pwm_changed.connect(self._serial_thread.set_pwm)
        self._pwm_panel.freq_changed.connect(self._serial_thread.set_freq)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_frame_ready(self, frame: np.ndarray) -> None:
        self._camera_widget.set_frame(frame)
        if self._camera_thread:
            self._camera_thread.mark_displayed()
        if self._video_recorder.is_recording:
            self._video_recorder.write_frame(frame)
            self._lbl_frames.setText(f"Frames: {self._video_recorder.frame_count}")

    def _on_frame_size_ready(self, w: int, h: int, fps: float) -> None:
        self._frame_w = w
        self._frame_h = h
        self._actual_fps = fps
        self._lbl_fps.setText(f"FPS: {fps:.1f}")
        self._status_bar.showMessage(f"Camera ready: {w}×{h} @ {fps:.1f} fps", 4000)

    def _on_serial_disconnected(self) -> None:
        self._btn_connect.setChecked(False)
        self._btn_connect.setText("Connect")
        self._ping_timer.stop()
        self._status_bar.showMessage("ESP32 disconnected")

    def _on_connect_toggled(self, checked: bool) -> None:
        if checked:
            port = self._port_combo.currentText()
            if not port:
                self._btn_connect.setChecked(False)
                return
            self._serial_thread.connect(port)
            self._btn_connect.setText("Disconnect")
            self._ping_timer.start()
        else:
            self._serial_thread.disconnect()
            self._btn_connect.setText("Connect")
            self._ping_timer.stop()

    def _on_record_toggled(self, recording: bool) -> None:
        if recording:
            label = self._session_name.text().strip().replace(" ", "_") or "session"
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            folder = Path("recordings") / f"{ts}_{label}"
            folder.mkdir(parents=True, exist_ok=True)
            self._session_folder = folder
            self._video_recorder.start(
                folder / "footage.mp4",
                fps=self._actual_fps,
                frame_size=(self._frame_w, self._frame_h),
            )
            self._btn_record.setText("■ Stop Recording")
            self._lbl_frames.setText("Frames: 0")
            self._status_bar.showMessage(f"Recording → {folder}")
        else:
            self._video_recorder.stop()
            self._btn_record.setText("● Start Recording")
            if self._session_folder:
                self._save_session_json(self._session_folder)
                self._status_bar.showMessage(
                    f"Saved {self._video_recorder.frame_count} frames to {self._session_folder}"
                )

    def _save_session_json(self, folder: Path) -> None:
        pwm = {
            str(i + 1): {
                "freq_hz": self._pwm_panel.current_freq(i + 1),
                "duty": self._pwm_panel.current_duty(i + 1),
            }
            for i in range(4)
        }
        session = Session(
            label=self._session_name.text().strip(),
            notes=self._session_notes.toPlainText().strip(),
            start_time=datetime.now().isoformat(),
            fps=30.0,
            frame_width=self._frame_w,
            frame_height=self._frame_h,
            total_frames=self._video_recorder.frame_count,
            pwm_settings=pwm,
        )
        session.save(folder)

    def _refresh_ports(self) -> None:
        current = self._port_combo.currentText()
        self._port_combo.clear()
        ports = SerialThread.available_ports()
        self._port_combo.addItems(ports)
        if current in ports:
            self._port_combo.setCurrentText(current)

    def _refresh_cameras(self) -> None:
        import cv2
        self._status_bar.showMessage("Scanning cameras — stopping live feed temporarily…")
        # Must stop the camera thread first; DSHOW can't share a camera on Windows
        self._camera_thread.stop_capture()
        self._camera_widget.setText("Scanning cameras…")

        self._camera_combo.clear()
        for i in range(8):
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    try:
                        cap.release()
                    except Exception:
                        pass
                    self._camera_combo.addItem(f"Camera {i}  ({w}×{h})", userData=i)
                else:
                    try:
                        cap.release()
                    except Exception:
                        pass
            except Exception:
                pass

        count = self._camera_combo.count()
        self._status_bar.showMessage(
            f"Found {count} camera(s). Select one and press Switch.", 4000
        )

        # Restart with whichever camera is now selected
        self._restart_camera_thread()

    def _on_switch_camera(self) -> None:
        self._camera_thread.stop_capture()
        self._restart_camera_thread()

    def _restart_camera_thread(self) -> None:
        index = self._camera_combo.currentData()
        if index is None:
            index = 0
        res = self._res_combo.currentData() or (1280, 720)
        self._camera_thread = CameraThread(
            camera_index=index, width=res[0], height=res[1]
        )
        self._camera_thread.frame_ready.connect(self._on_frame_ready)
        self._camera_thread.frame_size_ready.connect(self._on_frame_size_ready)
        self._camera_thread.camera_error.connect(
            lambda msg: self._status_bar.showMessage(f"Camera error: {msg}")
        )
        self._camera_thread.start_capture()
        self._lbl_fps.setText("FPS: measuring…")

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    _SETTINGS_PATH = Path(__file__).parent.parent / "app_settings.json"

    def _load_settings(self) -> None:
        if not self._SETTINGS_PATH.exists():
            return
        try:
            s = json.loads(self._SETTINGS_PATH.read_text())
        except Exception:
            return

        # Camera
        cam_idx = s.get("camera_index", 0)
        for i in range(self._camera_combo.count()):
            if self._camera_combo.itemData(i) == cam_idx:
                self._camera_combo.setCurrentIndex(i)
                break
        else:
            self._camera_combo.addItem(f"Camera {cam_idx}", userData=cam_idx)
            self._camera_combo.setCurrentIndex(self._camera_combo.count() - 1)

        # Resolution
        res = tuple(s.get("resolution", [1280, 720]))
        for i in range(self._res_combo.count()):
            if self._res_combo.itemData(i) == res:
                self._res_combo.setCurrentIndex(i)
                break

        # Serial port
        port = s.get("serial_port", "")
        if port:
            self._refresh_ports()
            idx = self._port_combo.findText(port)
            if idx >= 0:
                self._port_combo.setCurrentIndex(idx)

        # Session name & notes
        self._session_name.setText(s.get("session_name", ""))
        self._session_notes.setPlainText(s.get("session_notes", ""))

        # PWM state
        pwm_state = s.get("pwm_state")
        if pwm_state:
            self._pwm_panel.set_state(pwm_state)

    def _save_settings(self) -> None:
        res = self._res_combo.currentData() or (1280, 720)
        s = {
            "camera_index": self._camera_combo.currentData() or 0,
            "resolution": list(res),
            "serial_port": self._port_combo.currentText(),
            "session_name": self._session_name.text().strip(),
            "session_notes": self._session_notes.toPlainText().strip(),
            "pwm_state": self._pwm_panel.get_state(),
        }
        try:
            self._SETTINGS_PATH.write_text(json.dumps(s, indent=2))
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        if self._video_recorder.is_recording:
            self._video_recorder.stop()
            if self._session_folder:
                self._save_session_json(self._session_folder)
        self._save_settings()
        if self._camera_thread:
            self._camera_thread.stop_capture()
        if self._serial_thread.isRunning():
            self._serial_thread.disconnect()
        event.accept()
