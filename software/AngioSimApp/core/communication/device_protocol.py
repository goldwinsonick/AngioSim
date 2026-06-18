from __future__ import annotations

import json
from typing import Any, Dict


class DeviceProtocol:
    """
    Satu tempat untuk format command UART.

    Kalau format protokol berubah, edit file ini saja.
    GUI dan worker tidak perlu tahu detail JSON command.
    """

    @staticmethod
    def encode(seq: int, cmd: str, **payload: Any) -> str:
        packet: Dict[str, Any] = {"seq": seq, "cmd": cmd}
        packet.update(payload)
        return json.dumps(packet) + "\n"

    @staticmethod
    def decode(line: str) -> Dict[str, Any]:
        return json.loads(line)

    @staticmethod
    def start_device(seq: int) -> str:
        return DeviceProtocol.encode(seq, "START_DEVICE")

    @staticmethod
    def stop_device(seq: int) -> str:
        return DeviceProtocol.encode(seq, "STOP_DEVICE")

    @staticmethod
    def set_params(seq: int, heart_pwm: int, water_pwm: int) -> str:
        return DeviceProtocol.encode(seq, "SET_PARAMS", heart_pwm=heart_pwm, water_pwm=water_pwm)

    @staticmethod
    def ping(seq: int) -> str:
        return DeviceProtocol.encode(seq, "PING")

    @staticmethod
    def status(seq: int) -> str:
        return DeviceProtocol.encode(seq, "STATUS")
