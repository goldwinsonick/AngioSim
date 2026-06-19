from __future__ import annotations
from typing import Any
import numpy as np
import cv2
from core.pipeline import PipelineStage, ParamDescriptor


class ColorMask(PipelineStage):
    """Detects an HSV color/brightness range and stores the binary mask in
    context under a configurable name. Never modifies the frame.
    Use MaskApply to apply effects and MaskCombine to merge masks."""

    stage_name = "ColorMask"

    def __init__(self) -> None:
        super().__init__()
        self._mask_name: str = "mask"

    @property
    def name(self) -> str:
        return self.stage_name

    def get_text_params(self) -> list[tuple[str, str]]:
        return [("_mask_name", "Mask Name")]

    def get_params(self) -> list[ParamDescriptor]:
        return [
            ParamDescriptor("hue_min", "Hue Min", 0,   180, 0,   1, 0),
            ParamDescriptor("hue_max", "Hue Max", 0,   180, 180, 1, 0),
            ParamDescriptor("sat_min", "Sat Min", 0,   255, 0,   1, 0),
            ParamDescriptor("sat_max", "Sat Max", 0,   255, 255, 1, 0),
            ParamDescriptor("val_min", "Val Min", 0,   255, 0,   1, 0),
            ParamDescriptor("val_max", "Val Max", 0,   255, 255, 1, 0),
            ParamDescriptor("blur",    "Blur",    0,   20,  0,   1, 0),
            ParamDescriptor("dilate",  "Dilate",  0,   20,  0,   1, 0),
            ParamDescriptor("erode",   "Erode",   0,   20,  0,   1, 0),
            ParamDescriptor("invert",  "Invert",  0,   1,   0,   1, 0),
        ]

    def to_config(self) -> dict[str, Any]:
        cfg = super().to_config()
        cfg["mask_name"] = self._mask_name
        return cfg

    def from_config(self, cfg: dict[str, Any]) -> None:
        super().from_config(cfg)
        self._mask_name = str(cfg.get("mask_name", self._mask_name))

    def process(self, frame: np.ndarray, context: dict) -> np.ndarray:
        p = self._params

        src = frame if frame.ndim == 3 else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        hsv = cv2.cvtColor(src, cv2.COLOR_BGR2HSV)

        lo = np.array([p["hue_min"], p["sat_min"], p["val_min"]], dtype=np.uint8)
        hi = np.array([p["hue_max"], p["sat_max"], p["val_max"]], dtype=np.uint8)
        mask = cv2.inRange(hsv, lo, hi)

        blur = int(p["blur"])
        if blur > 0:
            k = blur * 2 + 1
            mask = cv2.GaussianBlur(mask, (k, k), 0)

        d = int(p["dilate"])
        e = int(p["erode"])
        if d > 0:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (d * 2 + 1, d * 2 + 1))
            mask = cv2.dilate(mask, k)
        if e > 0:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (e * 2 + 1, e * 2 + 1))
            mask = cv2.erode(mask, k)

        if int(p["invert"]):
            mask = cv2.bitwise_not(mask)

        context[self._mask_name] = mask
        return frame
