from __future__ import annotations
import numpy as np
import cv2
from core.pipeline import PipelineStage, ParamDescriptor


class FieldMask(PipelineStage):
    """Circular fluoroscopy field-of-view mask.
    Everything outside the circle is filled with outside_val (default black)."""

    stage_name = "FieldMask"

    def __init__(self) -> None:
        super().__init__()
        self._cached_mask: np.ndarray | None = None
        self._cached_shape: tuple = ()
        self._cached_params: tuple = ()

    @property
    def name(self) -> str:
        return self.stage_name

    def get_params(self) -> list[ParamDescriptor]:
        return [
            ParamDescriptor("center_x",   "Center X",    0.0, 1.0, 0.5,  0.01, 2),
            ParamDescriptor("center_y",   "Center Y",    0.0, 1.0, 0.5,  0.01, 2),
            ParamDescriptor("radius",     "Radius",      0.1, 1.0, 0.47, 0.01, 2),
            ParamDescriptor("softness",   "Softness px", 0,   60,  0,    1,    0),
            ParamDescriptor("outside_val","Outside",     0,   255, 0,    1,    0),
        ]

    def set_param_value(self, name: str, value: float) -> None:
        super().set_param_value(name, value)
        self._cached_mask = None

    def _build_mask(self, h: int, w: int) -> np.ndarray:
        cx = int(self._params["center_x"] * w)
        cy = int(self._params["center_y"] * h)
        r  = int(self._params["radius"] * min(w, h) / 2)
        soft = int(self._params["softness"])

        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, (cx, cy), r, 255, -1)

        if soft > 0:
            k = soft * 2 + 1
            mask = cv2.GaussianBlur(mask, (k, k), 0)

        return mask

    def process(self, frame: np.ndarray, context: dict) -> np.ndarray:
        h, w = frame.shape[:2]
        p = self._params
        key = (p["center_x"], p["center_y"], p["radius"], p["softness"])
        if self._cached_mask is None or self._cached_shape != (h, w) or self._cached_params != key:
            self._cached_mask = self._build_mask(h, w)
            self._cached_shape = (h, w)
            self._cached_params = key

        mask  = self._cached_mask.astype(np.float32) / 255.0
        out_v = int(p["outside_val"])

        if frame.ndim == 3:
            mask3 = mask[:, :, np.newaxis]
            outside = np.full_like(frame, out_v)
        else:
            mask3 = mask
            outside = np.full_like(frame, out_v)

        return np.clip(frame.astype(np.float32) * mask3 + outside * (1.0 - mask3), 0, 255).astype(np.uint8)
