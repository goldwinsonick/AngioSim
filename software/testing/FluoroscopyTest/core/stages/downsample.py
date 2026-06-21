from __future__ import annotations
import numpy as np
import cv2
from core.pipeline import PipelineStage, ParamDescriptor


class Downsample(PipelineStage):
    """Resize the frame to a smaller resolution for fast processing.
    Stores original size in context so Upsample can restore it."""

    stage_name = "Downsample"

    @property
    def name(self) -> str:
        return self.stage_name

    def get_params(self) -> list[ParamDescriptor]:
        return [
            ParamDescriptor("width",  "Width",  1, 4096, 512, 1, 0),
            ParamDescriptor("height", "Height", 1, 4096, 512, 1, 0),
        ]

    def process(self, frame: np.ndarray, context: dict) -> np.ndarray:
        h, w = frame.shape[:2]
        context["_pre_downsample_size"] = (w, h)
        tw = max(1, int(self._params["width"]))
        th = max(1, int(self._params["height"]))
        return cv2.resize(frame, (tw, th), interpolation=cv2.INTER_AREA)
