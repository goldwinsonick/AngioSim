import time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QStackedWidget, QVBoxLayout,
    QWidget,
)

# Mode indices for QComboBox / QStackedWidget
MODE_ALWAYS_ON = 0
MODE_SYSTOLE_DIASTOLE = 1
MODE_INTERVAL = 2


class DutySlider(QWidget):
    """Single duty-cycle slider paired with a spinbox (0–255)."""

    value_changed = pyqtSignal(int)

    def __init__(self, label: str = "", default: int = 0, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if label:
            layout.addWidget(QLabel(label))
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 255)
        self._slider.setValue(default)
        self._spin = QSpinBox()
        self._spin.setRange(0, 255)
        self._spin.setValue(default)
        self._spin.setFixedWidth(55)
        self._slider.valueChanged.connect(self._spin.setValue)
        self._slider.valueChanged.connect(self.value_changed)
        self._spin.valueChanged.connect(self._slider.setValue)
        layout.addWidget(self._slider)
        layout.addWidget(self._spin)

    def value(self) -> int:
        return self._slider.value()

    def set_value(self, v: int) -> None:
        self._slider.setValue(v)


class ChannelWidget(QGroupBox):
    """
    Controls for one PWM channel.
    Emits pwm_changed(value: int) whenever the effective duty cycle changes.
    Timing for Systole/Diastole and Interval modes is managed internally via QTimer.
    """

    pwm_changed = pyqtSignal(int)

    def __init__(
        self,
        channel: int,
        modes: list[str],
        parent=None,
    ):
        super().__init__(f"Ch {channel}", parent)
        self._channel = channel
        self._last_duty = -1

        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        # Mode selector
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        for m in modes:
            self._mode_combo.addItem(m)
        mode_row.addWidget(self._mode_combo)
        layout.addLayout(mode_row)

        # Stacked pages — one per mode
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        # Always On page
        self._always_on = DutySlider("Duty:", default=0)
        self._always_on.value_changed.connect(self._on_always_on_changed)
        self._stack.addWidget(self._always_on)

        # Systole/Diastole page
        if MODE_SYSTOLE_DIASTOLE < len(modes):
            sd_widget = QWidget()
            sd_layout = QVBoxLayout(sd_widget)
            sd_layout.setContentsMargins(0, 0, 0, 0)
            sd_layout.setSpacing(4)
            self._sys_slider = DutySlider("Systole:", default=200)
            self._dia_slider = DutySlider("Diastole:", default=0)
            sd_layout.addWidget(self._sys_slider)
            sd_layout.addWidget(self._dia_slider)
            bpm_row = QHBoxLayout()
            bpm_row.addWidget(QLabel("BPM:"))
            self._bpm_spin = QSpinBox()
            self._bpm_spin.setRange(10, 200)
            self._bpm_spin.setValue(60)
            bpm_row.addWidget(self._bpm_spin)
            sd_layout.addLayout(bpm_row)
            frac_row = QHBoxLayout()
            frac_row.addWidget(QLabel("Systole fraction:"))
            self._frac_spin = QDoubleSpinBox()
            self._frac_spin.setRange(0.05, 0.95)
            self._frac_spin.setSingleStep(0.05)
            self._frac_spin.setValue(0.35)
            frac_row.addWidget(self._frac_spin)
            sd_layout.addLayout(frac_row)
            self._stack.addWidget(sd_widget)

        # Interval page
        if MODE_INTERVAL < len(modes):
            iv_widget = QWidget()
            iv_layout = QVBoxLayout(iv_widget)
            iv_layout.setContentsMargins(0, 0, 0, 0)
            iv_layout.setSpacing(4)
            on_row = QHBoxLayout()
            on_row.addWidget(QLabel("ON time (ms):"))
            self._on_spin = QSpinBox()
            self._on_spin.setRange(50, 60000)
            self._on_spin.setValue(500)
            self._on_spin.setSingleStep(50)
            on_row.addWidget(self._on_spin)
            iv_layout.addLayout(on_row)
            off_row = QHBoxLayout()
            off_row.addWidget(QLabel("OFF time (ms):"))
            self._off_spin = QSpinBox()
            self._off_spin.setRange(50, 60000)
            self._off_spin.setValue(500)
            self._off_spin.setSingleStep(50)
            off_row.addWidget(self._off_spin)
            iv_layout.addLayout(off_row)
            on_duty_row = QHBoxLayout()
            on_duty_row.addWidget(QLabel("ON duty (0-255):"))
            self._iv_duty_spin = QSpinBox()
            self._iv_duty_spin.setRange(0, 255)
            self._iv_duty_spin.setValue(255)
            on_duty_row.addWidget(self._iv_duty_spin)
            iv_layout.addLayout(on_duty_row)
            self._stack.addWidget(iv_widget)

        self._mode_combo.currentIndexChanged.connect(self._stack.setCurrentIndex)

        # Internal timer for time-varying modes (50Hz tick)
        self._timer = QTimer(self)
        self._timer.setInterval(20)
        self._timer.timeout.connect(self._tick)
        self._cycle_start_ms = time.monotonic() * 1000

        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)

    # ------------------------------------------------------------------

    def activate(self, active: bool) -> None:
        """Start/stop the internal timer based on board enable state."""
        if active:
            self._cycle_start_ms = time.monotonic() * 1000
            self._timer.start()
        else:
            self._timer.stop()
            self._emit_if_changed(0)

    def current_duty(self) -> int:
        mode = self._mode_combo.currentIndex()
        if mode == MODE_ALWAYS_ON:
            return self._always_on.value()
        return self._last_duty if self._last_duty >= 0 else 0

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_always_on_changed(self, val: int) -> None:
        if self._mode_combo.currentIndex() == MODE_ALWAYS_ON:
            self._emit_if_changed(val)

    def _on_mode_changed(self, index: int) -> None:
        self._cycle_start_ms = time.monotonic() * 1000
        if index == MODE_ALWAYS_ON:
            self._emit_if_changed(self._always_on.value())

    def _tick(self) -> None:
        mode = self._mode_combo.currentIndex()
        now_ms = time.monotonic() * 1000

        if mode == MODE_SYSTOLE_DIASTOLE:
            bpm = self._bpm_spin.value()
            period_ms = 60_000.0 / bpm
            frac = self._frac_spin.value()
            elapsed = (now_ms - self._cycle_start_ms) % period_ms
            duty = self._sys_slider.value() if elapsed < period_ms * frac else self._dia_slider.value()
            self._emit_if_changed(duty)

        elif mode == MODE_INTERVAL:
            on_ms = self._on_spin.value()
            off_ms = self._off_spin.value()
            cycle_ms = on_ms + off_ms
            elapsed = (now_ms - self._cycle_start_ms) % cycle_ms
            duty = self._iv_duty_spin.value() if elapsed < on_ms else 0
            self._emit_if_changed(duty)

    def _emit_if_changed(self, duty: int) -> None:
        if duty != self._last_duty:
            self._last_duty = duty
            self.pwm_changed.emit(duty)


class PwmPanel(QGroupBox):
    """
    Master PWM control panel.
    Emits board_enable_changed and pwm_changed — never touches serial directly.
    """

    board_enable_changed = pyqtSignal(bool)
    pwm_changed = pyqtSignal(int, int)  # channel (1-4), value (0-255)

    def __init__(self, parent=None):
        super().__init__("PWM Control", parent)
        self._board_enabled = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Master enable button
        self._btn_enable = QPushButton("Enable Control Board")
        self._btn_enable.setCheckable(True)
        self._btn_enable.setStyleSheet(
            "QPushButton:checked { background-color: #c0392b; color: white; font-weight: bold; }"
            "QPushButton:!checked { background-color: #27ae60; color: white; font-weight: bold; }"
        )
        self._btn_enable.toggled.connect(self._on_board_toggled)
        layout.addWidget(self._btn_enable)

        # Channel widgets — all identical, fully configurable
        all_modes = ["Always On", "Systole/Diastole", "Interval"]

        self._ch1 = ChannelWidget(1, all_modes)
        self._ch2 = ChannelWidget(2, all_modes)
        self._ch3 = ChannelWidget(3, all_modes)
        self._ch4 = ChannelWidget(4, all_modes)

        self._channels = [self._ch1, self._ch2, self._ch3, self._ch4]

        for i, ch in enumerate(self._channels):
            layout.addWidget(ch)
            ch_num = i + 1
            ch.pwm_changed.connect(lambda val, n=ch_num: self.pwm_changed.emit(n, val))

    def _on_board_toggled(self, checked: bool) -> None:
        self._board_enabled = checked
        self._btn_enable.setText(
            "Disable Control Board" if checked else "Enable Control Board"
        )
        for ch in self._channels:
            ch.activate(checked)
        self.board_enable_changed.emit(checked)
        if checked:
            # Send current duties immediately
            for i, ch in enumerate(self._channels):
                self.pwm_changed.emit(i + 1, ch.current_duty())

    def current_duty(self, channel: int) -> int:
        """Returns the current duty for a 1-indexed channel."""
        return self._channels[channel - 1].current_duty()
