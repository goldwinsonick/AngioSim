from datetime import datetime
from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QMainWindow, QPushButton, QScrollArea, QSplitter,
    QStatusBar, QTabWidget, QVBoxLayout, QWidget,
)

from core.camera import CameraThread
from core.recorder import DataRecorder
from core.serial_comm import SerialThread
from utils.calibration import Calibration
from ui.camera_widget import CameraWidget
from ui.graph_widget import GraphWidget
from ui.pwm_panel import PwmPanel
from ui.tracking_panel import TrackingPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AngioSim — Cardiac Motion Controller")
        self.resize(1400, 820)

        self._calibration = Calibration()
        self._recorder = DataRecorder()
        self._calib_pending_mm: float | None = None

        self._camera_thread = CameraThread()
        self._serial_thread = SerialThread()

        self._pump_duty = 0
        self._valve_duty = 0

        self._setup_ui()
        self._connect_signals()

        # Ping ESP32 every 5s when connected
        self._ping_timer = QTimer(self)
        self._ping_timer.setInterval(5000)
        self._ping_timer.timeout.connect(self._serial_thread.ping)

        self._camera_thread.start_capture()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # ---- Left: camera + graph -----------------------------------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        self._camera_widget = CameraWidget()
        left_layout.addWidget(self._camera_widget, stretch=3)

        self._graph_widget = GraphWidget(window_seconds=10)
        self._graph_widget.setMinimumHeight(180)
        left_layout.addWidget(self._graph_widget, stretch=1)

        # Record controls row
        rec_row = QHBoxLayout()
        self._btn_record = QPushButton("Start Recording")
        self._btn_record.setCheckable(True)
        self._btn_record.setStyleSheet(
            "QPushButton:checked { background-color: #c0392b; color: white; font-weight: bold; }"
        )
        self._btn_record.toggled.connect(self._on_record_toggled)
        rec_row.addWidget(self._btn_record)

        btn_gen_graph = QPushButton("Generate Graph from CSV…")
        btn_gen_graph.clicked.connect(self._on_generate_graph)
        rec_row.addWidget(btn_gen_graph)

        btn_clear_graph = QPushButton("Clear Graph")
        btn_clear_graph.clicked.connect(self._graph_widget.clear_data)
        rec_row.addWidget(btn_clear_graph)

        left_layout.addLayout(rec_row)
        splitter.addWidget(left_widget)

        # ---- Right: controls ----------------------------------------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # Camera selector row
        camera_group = self._build_camera_row()
        right_layout.addWidget(camera_group)

        # Serial connection row
        serial_group = self._build_serial_row()
        right_layout.addWidget(serial_group)

        # Tabs: PWM | Tracking
        tabs = QTabWidget()
        self._pwm_panel = PwmPanel()
        self._tracking_panel = TrackingPanel()

        pwm_scroll = QScrollArea()
        pwm_scroll.setWidgetResizable(True)
        pwm_scroll.setWidget(self._pwm_panel)
        tabs.addTab(pwm_scroll, "PWM Control")
        tabs.addTab(self._tracking_panel, "Tracking")

        right_layout.addWidget(tabs, stretch=1)

        # Status info labels
        self._lbl_displacement = QLabel("Displacement: —")
        self._lbl_bpm = QLabel("BPM: —")
        self._lbl_area = QLabel("Area: —")
        for lbl in (self._lbl_displacement, self._lbl_bpm, self._lbl_area):
            lbl.setStyleSheet("font-size: 12px; color: #ccc;")
        right_layout.addWidget(self._lbl_displacement)
        right_layout.addWidget(self._lbl_bpm)
        right_layout.addWidget(self._lbl_area)

        splitter.addWidget(right_widget)
        splitter.setSizes([950, 430])

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Camera starting…")

    def _build_camera_row(self) -> QWidget:
        group = QWidget()
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)

        self._camera_combo = QComboBox()
        self._camera_combo.setMinimumWidth(110)

        btn_scan = QPushButton("Scan")
        btn_scan.setFixedWidth(50)
        btn_scan.setToolTip("Scan for connected cameras (may take a moment)")
        btn_scan.clicked.connect(self._refresh_cameras)

        btn_switch = QPushButton("Switch")
        btn_switch.setFixedWidth(55)
        btn_switch.clicked.connect(self._on_switch_camera)

        layout.addWidget(QLabel("Camera:"))
        layout.addWidget(self._camera_combo)
        layout.addWidget(btn_scan)
        layout.addWidget(btn_switch)
        layout.addStretch()

        # Populate with a basic list; full scan on demand
        for i in range(6):
            self._camera_combo.addItem(f"Camera {i}", userData=i)
        return group

    def _refresh_cameras(self) -> None:
        import cv2
        self._status_bar.showMessage("Scanning cameras…")
        self._camera_combo.clear()
        for i in range(8):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                self._camera_combo.addItem(f"Camera {i}  ({w}×{h})", userData=i)
        count = self._camera_combo.count()
        self._status_bar.showMessage(f"Found {count} camera(s). Select and press Switch.", 4000)

    def _on_switch_camera(self) -> None:
        index = self._camera_combo.currentData()
        if index is None:
            return
        self._camera_thread.stop_capture()
        self._camera_thread = CameraThread(camera_index=index)
        self._camera_thread.frame_ready.connect(self._on_frame_ready)
        self._camera_thread.tracking_result.connect(self._on_tracking_result)
        self._camera_thread.camera_error.connect(
            lambda msg: self._status_bar.showMessage(f"Camera error: {msg}")
        )
        self._camera_thread.start_capture()
        self._status_bar.showMessage(f"Switched to Camera {index}", 3000)

    def _build_serial_row(self) -> QWidget:
        group = QWidget()
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)

        self._port_combo = QComboBox()
        self._port_combo.setMinimumWidth(110)
        self._refresh_ports()

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setFixedWidth(60)
        btn_refresh.clicked.connect(self._refresh_ports)

        self._btn_connect = QPushButton("Connect")
        self._btn_connect.setCheckable(True)
        self._btn_connect.toggled.connect(self._on_connect_toggled)

        layout.addWidget(QLabel("Port:"))
        layout.addWidget(self._port_combo)
        layout.addWidget(btn_refresh)
        layout.addWidget(self._btn_connect)
        layout.addStretch()
        return group

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self):
        # Camera thread → UI
        self._camera_thread.frame_ready.connect(self._on_frame_ready)
        self._camera_thread.tracking_result.connect(self._on_tracking_result)
        self._camera_thread.camera_error.connect(
            lambda msg: self._status_bar.showMessage(f"Camera error: {msg}")
        )

        # Serial thread → UI
        self._serial_thread.ack_received.connect(self._on_ack_received)
        self._serial_thread.error_received.connect(
            lambda msg: self._status_bar.showMessage(f"Serial: {msg}")
        )
        self._serial_thread.connected.connect(
            lambda: self._status_bar.showMessage("ESP32 connected")
        )
        self._serial_thread.disconnected.connect(self._on_serial_disconnected)

        # PWM panel → serial
        self._pwm_panel.board_enable_changed.connect(self._on_board_enable_changed)
        self._pwm_panel.pwm_changed.connect(self._on_pwm_changed)

        # Tracking panel → camera thread
        self._tracking_panel.set_roi_requested.connect(
            self._camera_widget.begin_roi_draw
        )
        self._tracking_panel.set_line_requested.connect(
            self._camera_widget.begin_line_set
        )
        self._tracking_panel.clear_roi_requested.connect(
            lambda: self._camera_thread.set_roi(None)
        )
        self._tracking_panel.reset_reference_requested.connect(
            self._camera_thread.reset_reference
        )
        self._tracking_panel.threshold_changed.connect(
            self._camera_thread.set_thresholds
        )
        self._tracking_panel.morph_size_changed.connect(
            self._camera_thread.set_morph_kernel_size
        )
        self._tracking_panel.overlay_toggled.connect(
            self._camera_thread.set_show_overlay
        )
        self._tracking_panel.calibration_requested.connect(
            self._on_calibration_requested
        )
        self._tracking_panel.calib_line_requested.connect(
            self._camera_widget.begin_calib_line_set
        )

        # Camera widget interaction → camera thread
        self._camera_widget.roi_set.connect(self._on_roi_set)
        self._camera_widget.line_set.connect(self._on_line_set)
        self._camera_widget.calib_line_set.connect(self._on_calib_line_set)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_frame_ready(self, frame: np.ndarray) -> None:
        self._camera_widget.set_frame(frame)

    def _on_tracking_result(self, result: dict) -> None:
        d_mm = result.get("displacement_mm")
        d_px = result.get("displacement_px", 0.0)
        area = result.get("heart_area_px", 0)
        bpm = result.get("bpm_estimate")
        ts = result.get("timestamp", 0.0)

        if d_mm is not None:
            self._lbl_displacement.setText(f"Displacement: {d_mm:+.2f} mm")
            self._graph_widget.update_data(ts, d_mm)
        else:
            self._lbl_displacement.setText(f"Displacement: {d_px:+.1f} px (not calibrated)")

        self._lbl_bpm.setText(f"BPM: {bpm:.1f}" if bpm else "BPM: —")
        self._lbl_area.setText(f"Area: {area} px²")

        if self._recorder.is_recording:
            self._recorder.record(
                timestamp=ts,
                displacement_mm=d_mm,
                heart_area_px=area,
                pump_duty=self._pump_duty,
                valve_duty=self._valve_duty,
                bpm_estimate=bpm,
            )

    def _on_ack_received(self, ack: str) -> None:
        self._status_bar.showMessage(f"ESP32: {ack}", 2000)

    def _on_serial_disconnected(self) -> None:
        self._btn_connect.setChecked(False)
        self._btn_connect.setText("Connect")
        self._ping_timer.stop()
        self._status_bar.showMessage("ESP32 disconnected")

    def _on_board_enable_changed(self, enabled: bool) -> None:
        self._serial_thread.set_board_enable(enabled)

    def _on_pwm_changed(self, channel: int, value: int) -> None:
        self._serial_thread.set_pwm(channel, value)
        if channel == 1:
            self._pump_duty = value
        elif channel == 2:
            self._valve_duty = value

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

    def _on_roi_set(self, roi: tuple) -> None:
        self._camera_thread.set_roi(roi)
        self._status_bar.showMessage(f"ROI set: {roi}", 3000)

    def _on_line_set(self, p1: tuple, p2: tuple) -> None:
        self._camera_thread.set_line(p1, p2)
        self._status_bar.showMessage(f"Measurement line set: {p1} → {p2}", 3000)

    def _on_calibration_requested(self, dist_mm: float) -> None:
        self._calib_pending_mm = dist_mm
        self._status_bar.showMessage(
            f"Click two points spanning {dist_mm:.0f} mm on the image…"
        )

    def _on_calib_line_set(self, p1: tuple, p2: tuple) -> None:
        if self._calib_pending_mm is None:
            return
        self._calibration.set_reference(p1, p2, self._calib_pending_mm)
        self._calib_pending_mm = None
        px_per_mm = self._calibration.px_per_mm
        self._camera_thread.set_calibration(px_per_mm)
        self._tracking_panel.update_calibration_label(px_per_mm)
        self._status_bar.showMessage(
            f"Calibrated: {px_per_mm:.2f} px/mm", 4000
        )

    def _on_record_toggled(self, recording: bool) -> None:
        if recording:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"angiosim_{ts}.csv"
            path, _ = QFileDialog.getSaveFileName(
                self, "Save CSV", default_name, "CSV Files (*.csv)"
            )
            if not path:
                self._btn_record.setChecked(False)
                return
            self._recorder.start(Path(path))
            self._btn_record.setText("Stop Recording")
            self._status_bar.showMessage(f"Recording to {path}")
        else:
            self._recorder.stop()
            self._btn_record.setText("Start Recording")
            self._status_bar.showMessage("Recording stopped")

    def _on_generate_graph(self) -> None:
        csv_path, _ = QFileDialog.getOpenFileName(
            self, "Open CSV", "", "CSV Files (*.csv)"
        )
        if not csv_path:
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Graph Image", csv_path.replace(".csv", ".png"),
            "PNG Images (*.png);;All Files (*)"
        )
        DataRecorder.generate_graph(
            Path(csv_path),
            Path(save_path) if save_path else None,
        )
        if save_path:
            self._status_bar.showMessage(f"Graph saved to {save_path}", 4000)

    def _refresh_ports(self) -> None:
        current = self._port_combo.currentText()
        self._port_combo.clear()
        ports = SerialThread.available_ports()
        self._port_combo.addItems(ports)
        if current in ports:
            self._port_combo.setCurrentText(current)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._camera_thread.stop_capture()
        if self._serial_thread.isRunning():
            self._serial_thread.disconnect()
        if self._recorder.is_recording:
            self._recorder.stop()
        event.accept()
