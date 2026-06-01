from __future__ import annotations

import queue
import time
from typing import Dict

from PyQt6.QtCore import QThread, pyqtSignal

from core.communication.device_protocol import DeviceProtocol

try:
    import serial
except ImportError:
    serial = None


class UARTWorker(QThread):
    """
    Low-level serial worker.

    File ini tidak tahu tentang tombol GUI atau halaman GUI.
    Tugasnya hanya:
    - buka/tutup serial port
    - kirim command JSON
    - baca balasan board
    - emit signal ke controller
    """

    connected_changed = pyqtSignal(bool, str)
    packet_received = pyqtSignal(dict)
    error_received = pyqtSignal(str)
    log_received = pyqtSignal(str)

    def __init__(self, config: Dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.mode = str(config.get("mode", "mock")).lower()

        self._running = False
        self._serial = None
        self._seq = 0
        self._tx_queue: "queue.Queue[str]" = queue.Queue()

        params = config.get("parameters", {})
        self._mock_device_on = False
        self._mock_heart_pwm = int(params.get("heart_pump_pwm", 125))
        self._mock_water_pwm = int(params.get("water_pump_pwm", 100))

        self._last_ping_time = 0.0
        self._last_status_time = 0.0

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def send_raw_line(self, line: str) -> None:
        self._tx_queue.put(line)

    def stop_worker(self) -> None:
        self._running = False

    def run(self) -> None:
        self._running = True

        if self.mode == "mock":
            self._run_mock()
        else:
            self._run_hardware()

    # -----------------------------
    # Mock mode
    # -----------------------------

    def _run_mock(self) -> None:
        self.connected_changed.emit(True, "MOCK MODE")
        self._emit_mock_status()

        while self._running:
            while not self._tx_queue.empty():
                line = self._tx_queue.get()
                self.log_received.emit("TX MOCK: " + line.strip())

                try:
                    packet = DeviceProtocol.decode(line)
                    self._handle_mock_packet(packet)
                except Exception as exc:
                    self.error_received.emit(f"Mock decode error: {exc}")

            interval = self.config.get("device", {}).get("status_interval_ms", 1000) / 1000.0
            now = time.time()
            if now - self._last_status_time >= interval:
                self._emit_mock_status()
                self._last_status_time = now

            self.msleep(20)

        self.connected_changed.emit(False, "Mock stopped")

    def _handle_mock_packet(self, packet: Dict) -> None:
        seq = packet.get("seq", -1)
        cmd = str(packet.get("cmd", "")).upper()

        if cmd == "PING":
            self._emit_ack(seq, cmd, True, "mock_available")

        elif cmd == "SET_PARAMS":
            self._mock_heart_pwm = self._clamp_pwm(packet.get("heart_pwm", self._mock_heart_pwm))
            self._mock_water_pwm = self._clamp_pwm(packet.get("water_pwm", self._mock_water_pwm))
            self._emit_ack(seq, cmd, True, "parameters_updated")

        elif cmd == "START_DEVICE":
            self._mock_device_on = True
            self._emit_ack(seq, cmd, True, "device_started")

        elif cmd == "STOP_DEVICE":
            self._mock_device_on = False
            self._emit_ack(seq, cmd, True, "device_stopped")

        elif cmd == "STATUS":
            pass

        else:
            self._emit_ack(seq, cmd, False, "unknown_command")

        self._emit_mock_status()

    def _emit_ack(self, seq: int, cmd: str, ok: bool, msg: str) -> None:
        self.packet_received.emit({
            "type": "ACK",
            "seq": seq,
            "cmd": cmd,
            "ok": ok,
            "msg": msg,
        })

    def _emit_mock_status(self) -> None:
        self.packet_received.emit({
            "type": "STATUS",
            "device": "ON" if self._mock_device_on else "OFF",
            "phase": "DIASTOLE" if self._mock_device_on else "IDLE",
            "heart_pwm": self._mock_heart_pwm,
            "water_pwm": self._mock_water_pwm,
        })

    @staticmethod
    def _clamp_pwm(value: int) -> int:
        return max(0, min(255, int(value)))

    # -----------------------------
    # Hardware mode
    # -----------------------------

    def _run_hardware(self) -> None:
        if serial is None:
            self.error_received.emit("pyserial belum ter-install. Jalankan: pip install pyserial")
            self.connected_changed.emit(False, "pyserial missing")
            return

        while self._running:
            if self._serial is None:
                self._open_serial()

            if self._serial is None:
                delay_ms = int(self.config.get("serial", {}).get("reconnect_interval_sec", 2.0) * 1000)
                self.msleep(delay_ms)
                continue

            try:
                self._process_tx()
                self._read_rx()
                self._auto_ping()
            except Exception as exc:
                self.error_received.emit(f"Koneksi serial bermasalah: {exc}")
                self._close_serial()
                self.connected_changed.emit(False, "UART disconnected")

            self.msleep(10)

        self._close_serial()
        self.connected_changed.emit(False, "UART stopped")

    def _open_serial(self) -> None:
        port = self.config.get("serial", {}).get("port", "COM3")
        baudrate = int(self.config.get("serial", {}).get("baudrate", 115200))
        timeout = float(self.config.get("serial", {}).get("read_timeout_sec", 0.1))

        try:
            self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
            self.connected_changed.emit(True, f"Connected to {port} @ {baudrate}")
        except Exception as exc:
            self._serial = None
            self.connected_changed.emit(False, f"Cannot open {port}: {exc}")

    def _close_serial(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None

    def _process_tx(self) -> None:
        if self._serial is None:
            return

        while not self._tx_queue.empty():
            line = self._tx_queue.get()
            self._serial.write(line.encode("utf-8"))
            self.log_received.emit("TX: " + line.strip())

    def _read_rx(self) -> None:
        if self._serial is None:
            return

        raw = self._serial.readline()
        if not raw:
            return

        line = raw.decode("utf-8", errors="ignore").strip()
        if not line:
            return

        self.log_received.emit("RX: " + line)

        try:
            packet = DeviceProtocol.decode(line)
            self.packet_received.emit(packet)
        except Exception:
            self.error_received.emit("Data dari board bukan JSON valid.")
            self.log_received.emit("Invalid JSON: " + line)

    def _auto_ping(self) -> None:
        ping_interval = self.config.get("device", {}).get("auto_ping_interval_ms", 1000) / 1000.0
        now = time.time()

        if now - self._last_ping_time >= ping_interval:
            seq = self.next_seq()
            self.send_raw_line(DeviceProtocol.ping(seq))
            self._last_ping_time = now
