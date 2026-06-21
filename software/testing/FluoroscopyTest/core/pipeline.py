from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
import time
import numpy as np


@dataclass
class ParamDescriptor:
    name: str
    label: str
    min_val: float
    max_val: float
    default: float
    step: float = 0.01
    decimals: int = 2


class PipelineStage(ABC):
    def __init__(self) -> None:
        self.enabled: bool = True
        self._params: dict[str, float] = {
            p.name: p.default for p in self.get_params()
        }

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def process(self, frame: np.ndarray, context: dict) -> np.ndarray: ...

    @abstractmethod
    def get_params(self) -> list[ParamDescriptor]: ...

    def get_path_params(self) -> list[tuple[str, str, str]]:
        """Returns list of (attr_name, label, file_filter) for file-path fields."""
        return []

    def get_text_params(self) -> list[tuple[str, str]]:
        """Returns list of (attr_name, label) for free-text string fields."""
        return []

    def get_param_value(self, name: str) -> float:
        return self._params[name]

    def set_param_value(self, name: str, value: float) -> None:
        self._params[name] = value

    def to_config(self) -> dict[str, Any]:
        cfg: dict[str, Any] = {
            "name": self.name,
            "enabled": self.enabled,
            "params": dict(self._params),
        }
        for attr_name, _ in self.get_text_params():
            cfg[attr_name.lstrip("_")] = getattr(self, attr_name, "")
        return cfg

    def from_config(self, cfg: dict[str, Any]) -> None:
        self.enabled = cfg.get("enabled", True)
        for k, v in cfg.get("params", {}).items():
            if k in self._params:
                self._params[k] = float(v)
        for attr_name, _ in self.get_text_params():
            key = attr_name.lstrip("_")
            if key in cfg:
                setattr(self, attr_name, str(cfg[key]))


class Pipeline:
    def __init__(self) -> None:
        self._stages: list[PipelineStage] = []

    @property
    def stages(self) -> list[PipelineStage]:
        return list(self._stages)

    def add_stage(self, stage: PipelineStage) -> None:
        self._stages.append(stage)

    def remove_stage(self, index: int) -> None:
        self._stages.pop(index)

    def move_stage(self, from_index: int, to_index: int) -> None:
        stage = self._stages.pop(from_index)
        self._stages.insert(to_index, stage)

    def process(self, frame: np.ndarray) -> tuple[list[np.ndarray], list[float]]:
        """Returns (frames, timings_ms).
        frames[0] = raw, frames[N] = output of stage N.
        timings_ms[N] = ms for stage N (0.0 if disabled)."""
        frames: list[np.ndarray] = [frame]
        timings: list[float] = []
        context: dict = {}
        current = frame
        for stage in self._stages:
            if stage.enabled:
                t0 = time.perf_counter()
                current = stage.process(current, context)
                timings.append((time.perf_counter() - t0) * 1000.0)
            else:
                timings.append(0.0)
            frames.append(current)
        return frames, timings

    def to_config(self) -> list[dict[str, Any]]:
        return [s.to_config() for s in self._stages]

    def from_config(self, cfg_list: list[dict[str, Any]], registry: dict[str, type]) -> None:
        self._stages.clear()
        for cfg in cfg_list:
            cls = registry.get(cfg["name"])
            if cls is None:
                continue
            stage = cls()
            stage.from_config(cfg)
            self._stages.append(stage)
