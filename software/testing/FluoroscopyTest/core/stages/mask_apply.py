from __future__ import annotations
from typing import Any
import numpy as np
import cv2
from core.pipeline import PipelineStage, ParamDescriptor


class MaskApply(PipelineStage):
    """Applies a visual effect to a named mask stored in the pipeline context."""

    stage_name = "MaskApply"

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
            ParamDescriptor("effect",    "Effect",    0,   3,   0,    1,    0),
            ParamDescriptor("intensity", "Intensity", 0.0, 1.0, 0.5,  0.01, 2),
            ParamDescriptor("tint_hue",  "Tint Hue",  0,   180, 60,   1,    0),
        ]

    def to_config(self) -> dict[str, Any]:
        cfg = super().to_config()
        cfg["mask_name"] = self._mask_name
        return cfg

    def from_config(self, cfg: dict[str, Any]) -> None:
        super().from_config(cfg)
        self._mask_name = str(cfg.get("mask_name", self._mask_name))

    def process(self, frame: np.ndarray, context: dict) -> np.ndarray:
        mask = context.get(self._mask_name)
        if mask is None:
            return frame

        effect    = int(self._params["effect"])
        intensity = self._params["intensity"]
        tint_hue  = int(self._params["tint_hue"])

        if frame.ndim == 2:
            base = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        else:
            base = frame

        if mask.shape[:2] != base.shape[:2]:
            mask = cv2.resize(mask, (base.shape[1], base.shape[0]),
                              interpolation=cv2.INTER_NEAREST)

        bool_mask = mask > 0   # 2D bool (h, w)

        if effect == 0:   # Tint
            bgr_color = cv2.cvtColor(
                np.array([[[tint_hue, 255, 255]]], dtype=np.uint8),
                cv2.COLOR_HSV2BGR
            )[0, 0].tolist()
            solid   = np.full_like(base, bgr_color)
            blended = np.where(bool_mask[:, :, np.newaxis], solid, base)
            return cv2.addWeighted(blended, intensity, base, 1.0 - intensity, 0)

        elif effect == 1:  # Darken
            darkened = cv2.convertScaleAbs(base, alpha=(1.0 - intensity))
            result   = base.copy()
            result[bool_mask] = darkened[bool_mask]
            return result

        elif effect == 2:  # Brighten
            brightened = cv2.convertScaleAbs(base, alpha=1.0, beta=int(intensity * 255))
            result     = base.copy()
            result[bool_mask] = brightened[bool_mask]
            return result

        else:   # Isolate
            result = np.zeros_like(base)
            result[bool_mask] = base[bool_mask]
            return result
