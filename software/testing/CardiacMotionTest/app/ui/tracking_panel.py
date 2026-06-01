from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSlider, QSpinBox, QCheckBox, QInputDialog,
)
from PyQt6.QtCore import Qt


class TrackingPanel(QGroupBox):
    set_roi_requested = pyqtSignal()
    set_line_requested = pyqtSignal()
    clear_roi_requested = pyqtSignal()
    reset_reference_requested = pyqtSignal()
    threshold_changed = pyqtSignal(int, int)   # lower, upper
    morph_size_changed = pyqtSignal(int, int)  # open_k, close_k
    overlay_toggled = pyqtSignal(bool)
    calibration_requested = pyqtSignal(float)  # physical distance mm
    calib_line_requested = pyqtSignal()        # triggers camera widget line-set in calib mode

    def __init__(self, parent=None):
        super().__init__("Tracking & Calibration", parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ROI controls
        roi_row = QHBoxLayout()
        btn_roi = QPushButton("Draw ROI")
        btn_roi.setToolTip("Click and drag on the camera feed to define the region of interest")
        btn_roi.clicked.connect(self.set_roi_requested)
        btn_clear_roi = QPushButton("Clear ROI")
        btn_clear_roi.clicked.connect(self.clear_roi_requested)
        roi_row.addWidget(btn_roi)
        roi_row.addWidget(btn_clear_roi)
        layout.addLayout(roi_row)

        # Measurement line
        btn_line = QPushButton("Set Measurement Line (2 clicks)")
        btn_line.setToolTip("Click two points on the camera feed to define the vertical measurement axis")
        btn_line.clicked.connect(self.set_line_requested)
        layout.addWidget(btn_line)

        # Reset displacement reference
        btn_reset = QPushButton("Reset Displacement Reference")
        btn_reset.setToolTip("Resets the zero reference point to the current heart position")
        btn_reset.clicked.connect(self.reset_reference_requested)
        layout.addWidget(btn_reset)

        layout.addWidget(self._separator())

        # Thresholds
        layout.addWidget(QLabel("White threshold (lower / upper):"))
        thresh_row = QHBoxLayout()
        self._lower_spin = QSpinBox()
        self._lower_spin.setRange(0, 254)
        self._lower_spin.setValue(160)
        self._lower_spin.valueChanged.connect(self._emit_threshold)
        self._upper_spin = QSpinBox()
        self._upper_spin.setRange(1, 255)
        self._upper_spin.setValue(255)
        self._upper_spin.valueChanged.connect(self._emit_threshold)
        thresh_row.addWidget(self._lower_spin)
        thresh_row.addWidget(QLabel("–"))
        thresh_row.addWidget(self._upper_spin)
        layout.addLayout(thresh_row)

        # Morphology
        layout.addWidget(QLabel("Morph kernel (open / close):"))
        morph_row = QHBoxLayout()
        self._open_spin = QSpinBox()
        self._open_spin.setRange(1, 31)
        self._open_spin.setSingleStep(2)
        self._open_spin.setValue(5)
        self._open_spin.valueChanged.connect(self._emit_morph)
        self._close_spin = QSpinBox()
        self._close_spin.setRange(1, 31)
        self._close_spin.setSingleStep(2)
        self._close_spin.setValue(7)
        self._close_spin.valueChanged.connect(self._emit_morph)
        morph_row.addWidget(self._open_spin)
        morph_row.addWidget(QLabel("/"))
        morph_row.addWidget(self._close_spin)
        layout.addLayout(morph_row)

        # Overlay toggle
        self._chk_overlay = QCheckBox("Show tracking overlay")
        self._chk_overlay.setChecked(True)
        self._chk_overlay.toggled.connect(self.overlay_toggled)
        layout.addWidget(self._chk_overlay)

        layout.addWidget(self._separator())

        # Calibration
        calib_layout = QHBoxLayout()
        self._calib_dist_spin = QSpinBox()
        self._calib_dist_spin.setRange(1, 500)
        self._calib_dist_spin.setValue(30)
        self._calib_dist_spin.setSuffix(" mm")
        calib_layout.addWidget(QLabel("Known dist:"))
        calib_layout.addWidget(self._calib_dist_spin)
        layout.addLayout(calib_layout)

        btn_calib = QPushButton("Calibrate (click 2 points)")
        btn_calib.setToolTip("Set the reference distance above, then click two points that span that distance on the image")
        btn_calib.clicked.connect(self._on_calibrate_clicked)
        layout.addWidget(btn_calib)

        self._calib_label = QLabel("Not calibrated")
        self._calib_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self._calib_label)

        layout.addStretch()

    def _emit_threshold(self):
        self.threshold_changed.emit(self._lower_spin.value(), self._upper_spin.value())

    def _emit_morph(self):
        self.morph_size_changed.emit(self._open_spin.value(), self._close_spin.value())

    def _on_calibrate_clicked(self):
        dist_mm = float(self._calib_dist_spin.value())
        self.calibration_requested.emit(dist_mm)
        self.calib_line_requested.emit()

    def update_calibration_label(self, px_per_mm: float | None) -> None:
        if px_per_mm is None:
            self._calib_label.setText("Not calibrated")
        else:
            self._calib_label.setText(f"Calibrated: {px_per_mm:.2f} px/mm")

    @staticmethod
    def _separator():
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #444;")
        return sep
