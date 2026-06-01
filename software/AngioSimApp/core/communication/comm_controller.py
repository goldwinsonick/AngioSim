from __future__ import annotations

from typing import Dict

from PyQt6.QtCore import QObject, pyqtSignal

from core.communication.device_protocol import DeviceProtocol
from core.communication.uart_worker import UARTWorker
from core.settings.device_settings import DeviceSettings


class CommController(QObject):
    """
    High-level communication controller.

    GUI cukup berhubungan dengan class ini.
    Serial, JSON, YAML, dan worker thread disembunyikan di sini.

    Public methods untuk GUI:
    - start()
    - shutdown()
    - start_device()
    - stop_device()
    - save_parameters(...)
    - reset_default_parameters()
    """

    device_started = pyqtSignal()
    device_stopped = pyqtSignal()
    parameters_saved = pyqtSignal(dict)
    parameters_reset = pyqtSignal(dict)
    error_message = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, config_path: str = "config/device_config.yaml", parent=None):
        super().__init__(parent)

        self.settings = DeviceSettings(config_path)
        self.config: Dict = self.settings.load()

        self.worker = UARTWorker(self.config)
        self.worker.connected_changed.connect(self._on_connection_changed)
        self.worker.packet_received.connect(self._on_packet_received)
        self.worker.error_received.connect(self.error_message)
        self.worker.log_received.connect(self.log_message)

    def start(self) -> None:
        self.worker.start()

    def shutdown(self) -> None:
        self.worker.stop_worker()
        self.worker.wait(1000)

    def start_device(self) -> None:
        seq = self.worker.next_seq()
        self.worker.send_raw_line(DeviceProtocol.start_device(seq))

    def stop_device(self) -> None:
        seq = self.worker.next_seq()
        self.worker.send_raw_line(DeviceProtocol.stop_device(seq))

    def save_parameters(self, heart_pump_pwm: int, water_pump_pwm: int) -> None:
        params = self.settings.save_parameters(heart_pump_pwm, water_pump_pwm)

        seq = self.worker.next_seq()
        self.worker.send_raw_line(
            DeviceProtocol.set_params(
                seq,
                heart_pwm=params["heart_pump_pwm"],
                water_pwm=params["water_pump_pwm"],
            )
        )

        self.parameters_saved.emit(params)

    def reset_default_parameters(self) -> None:
        params = self.settings.reset_default_parameters()

        seq = self.worker.next_seq()
        self.worker.send_raw_line(
            DeviceProtocol.set_params(
                seq,
                heart_pwm=params["heart_pump_pwm"],
                water_pwm=params["water_pump_pwm"],
            )
        )

        self.parameters_reset.emit(params)

    def get_parameters(self) -> Dict[str, int]:
        return self.settings.get_parameters()

    def _on_connection_changed(self, connected: bool, message: str) -> None:
        # Disimpan sebagai log internal, tidak wajib ditampilkan sebagai indikator user.
        self.log_message.emit(f"Connection: {connected} | {message}")

    def _on_packet_received(self, packet: Dict) -> None:
        msg_type = str(packet.get("type", "")).upper()

        if msg_type == "ACK":
            cmd = str(packet.get("cmd", ""))
            ok = bool(packet.get("ok", False))
            msg = str(packet.get("msg", ""))

            self.log_message.emit(f"ACK {cmd}: ok={ok}, msg={msg}")

            if not ok:
                self.error_message.emit(f"Device command gagal: {cmd} ({msg})")
                return

            if cmd == "START_DEVICE":
                self.device_started.emit()

            elif cmd == "STOP_DEVICE":
                self.device_stopped.emit()

        elif msg_type == "STATUS":
            self.log_message.emit(f"STATUS: {packet}")

        elif msg_type == "ERROR":
            self.error_message.emit(str(packet.get("msg", "Device error")))

        elif msg_type == "BOOT":
            self.log_message.emit(str(packet.get("msg", "Board ready")))

        else:
            self.log_message.emit(f"Packet: {packet}")
