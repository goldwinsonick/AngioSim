import queue
import serial
import serial.tools.list_ports
from PyQt6.QtCore import QThread, pyqtSignal


class SerialThread(QThread):
    ack_received = pyqtSignal(str)
    error_received = pyqtSignal(str)
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._port: serial.Serial | None = None
        self._cmd_queue: queue.Queue[str] = queue.Queue()
        self._running = False

    # ------------------------------------------------------------------
    # Public API (called from UI thread)
    # ------------------------------------------------------------------

    def connect(self, port: str, baud: int = 115200) -> None:
        if self._running:
            return
        try:
            self._port = serial.Serial(port, baud, timeout=0.05)
        except serial.SerialException as e:
            self.error_received.emit(f"Cannot open {port}: {e}")
            return
        self._running = True
        self.start()
        self.connected.emit()

    def disconnect(self) -> None:
        self._running = False
        self.wait(2000)
        if self._port and self._port.is_open:
            self._port.close()
        self._port = None
        self.disconnected.emit()

    def send_command(self, command: str) -> None:
        self._cmd_queue.put(command.rstrip("\n") + "\n")

    def set_pwm(self, channel: int, value: int) -> None:
        self.send_command(f"SET_PWM:{channel}:{value}")

    def set_board_enable(self, enabled: bool) -> None:
        self.send_command(f"BOARD_ENABLE:{1 if enabled else 0}")

    def ping(self) -> None:
        self.send_command("PING")

    # ------------------------------------------------------------------
    # QThread.run — serial thread body
    # ------------------------------------------------------------------

    def run(self) -> None:
        while self._running:
            # Send queued commands
            try:
                cmd = self._cmd_queue.get(timeout=0.001)
                if self._port and self._port.is_open:
                    self._port.write(cmd.encode())
            except queue.Empty:
                pass
            except serial.SerialException:
                self._running = False
                self.disconnected.emit()
                return

            # Read incoming responses
            try:
                if self._port and self._port.in_waiting:
                    line = self._port.readline().decode(errors="replace").strip()
                    if line.startswith("ACK:"):
                        self.ack_received.emit(line)
                    elif line.startswith("ERR:"):
                        self.error_received.emit(line)
                    elif line == "READY":
                        self.ack_received.emit("ACK:READY")
            except serial.SerialException:
                self._running = False
                self.disconnected.emit()
                return

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def available_ports() -> list[str]:
        return [p.device for p in serial.tools.list_ports.comports()]
