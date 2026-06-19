from __future__ import annotations
import numpy as np
import cv2
from core.pipeline import PipelineStage, ParamDescriptor


class Vignette(PipelineStage):
    stage_name = "Vignette"

    def __init__(self) -> None:
        super().__init__()
        self._cached_map: np.ndarray | None = None
        self._cached_shape: tuple = ()
        self._cached_params: tuple = ()

    @property
    def name(self) -> str:
        return self.stage_name

    def get_params(self) -> list[ParamDescriptor]:
        return [
            ParamDescriptor("strength", "Strength", 0.0, 1.0, 0.7, 0.01, 2),
            ParamDescriptor("radius",   "Radius",   0.1, 1.5, 0.7, 0.01, 2),
            ParamDescriptor("feather",  "Feather",  0.1, 2.0, 0.4, 0.01, 2),
        ]

    def set_param_value(self, name: str, value: float) -> None:
        super().set_param_value(name, value)
        self._cached_map = None

    def _build_map(self, h: int, w: int) -> np.ndarray:
        strength = self._params["strength"]
        radius   = self._params["radius"]
        feather  = max(self._params["feather"], 0.01)

        cy, cx = h / 2.0, w / 2.0
        Y, X = np.mgrid[0:h, 0:w]
        dist = np.sqrt(((X - cx) / cx) ** 2 + ((Y - cy) / cy) ** 2)
        t = np.clip((dist - radius) / feather, 0.0, 1.0)
        vignette = 1.0 - t * strength
        return vignette.astype(np.float32)

    def process(self, frame: np.ndarray, context: dict) -> np.ndarray:
        h, w = frame.shape[:2]
        key = (self._params["strength"], self._params["radius"], self._params["feather"])
        if self._cached_map is None or self._cached_shape != (h, w) or self._cached_params != key:
            self._cached_map = self._build_map(h, w)
            self._cached_shape = (h, w)
            self._cached_params = key

        vmap = self._cached_map
        if frame.ndim == 3:
            vmap = vmap[:, :, np.newaxis]
        return np.clip(frame.astype(np.float32) * vmap, 0, 255).astype(np.uint8)
