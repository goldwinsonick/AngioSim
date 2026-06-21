from __future__ import annotations
import numpy as np
import cv2
from core.pipeline import PipelineStage, ParamDescriptor


class Grain(PipelineStage):
    stage_name = "Grain"

    @property
    def name(self) -> str:
        return self.stage_name

    def get_params(self) -> list[ParamDescriptor]:
        return [
            ParamDescriptor("amount",     "Amount",     0, 100, 20, 1, 0),
            ParamDescriptor("monochrome", "Monochrome", 0, 1,   1,  1, 0),
        ]

    def process(self, frame: np.ndarray, context: dict) -> np.ndarray:
        amount = int(self._params["amount"])
        if amount == 0:
            return frame

        h, w = frame.shape[:2]
        mono = int(self._params["monochrome"])

        # cv2.randn is C++ optimized — much faster than np.random.normal
        if mono or frame.ndim == 2:
            noise = np.empty((h, w), dtype=np.float32)
            cv2.randn(noise, 0, float(amount))
            if frame.ndim == 3:
                noise = noise[:, :, np.newaxis]   # broadcast across channels
        else:
            noise = np.empty(frame.shape, dtype=np.float32)
            cv2.randn(noise, 0, float(amount))

        return cv2.convertScaleAbs(
            frame.astype(np.float32) + noise
        )
