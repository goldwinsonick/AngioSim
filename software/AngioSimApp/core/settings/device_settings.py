from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULT_CONFIG: Dict[str, Any] = {
    "mode": "mock",
    "serial": {
        "port": "COM3",
        "baudrate": 115200,
        "read_timeout_sec": 0.1,
        "reconnect_interval_sec": 2.0,
    },
    "device": {
        "auto_ping_interval_ms": 1000,
        "status_interval_ms": 1000,
    },
    "parameters": {
        "heart_pump_pwm": 125,
        "water_pump_pwm": 100,
    },
}


class DeviceSettings:
    def __init__(self, config_path: str | Path = "config/device_config.yaml"):
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = deepcopy(DEFAULT_CONFIG)

    def load(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            self.config = deepcopy(DEFAULT_CONFIG)
            self.save()
            return self.config

        with self.config_path.open("r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}

        self.config = self._deep_merge(deepcopy(DEFAULT_CONFIG), user_config)
        return self.config

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with self.config_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(self.config, f, sort_keys=False, allow_unicode=True)

    def get_parameters(self) -> Dict[str, int]:
        params = self.config.setdefault("parameters", {})

        return {
            "heart_pump_pwm": int(
                params.get("heart_pump_pwm", DEFAULT_CONFIG["parameters"]["heart_pump_pwm"])
            ),
            "water_pump_pwm": int(
                params.get("water_pump_pwm", DEFAULT_CONFIG["parameters"]["water_pump_pwm"])
            ),
        }

    def save_parameters(self, heart_pump_pwm: int, water_pump_pwm: int) -> Dict[str, int]:
        heart_pump_pwm = self._clamp_pwm(heart_pump_pwm)
        water_pump_pwm = self._clamp_pwm(water_pump_pwm)

        self.config.setdefault("parameters", {})
        self.config["parameters"]["heart_pump_pwm"] = heart_pump_pwm
        self.config["parameters"]["water_pump_pwm"] = water_pump_pwm

        self.save()
        return self.get_parameters()

    def reset_default_parameters(self) -> Dict[str, int]:
        self.config["parameters"] = deepcopy(DEFAULT_CONFIG["parameters"])
        self.save()
        return self.get_parameters()

    def get_mode(self) -> str:
        return str(self.config.get("mode", DEFAULT_CONFIG["mode"])).lower()

    @staticmethod
    def _clamp_pwm(value: int) -> int:
        return max(0, min(255, int(value)))

    @staticmethod
    def _deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(base)

        for key, value in update.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = DeviceSettings._deep_merge(result[key], value)
            else:
                result[key] = value

        return result