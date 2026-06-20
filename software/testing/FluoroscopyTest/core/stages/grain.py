from __future__ import annotations
import numpy as np
from core.pipeline import PipelineStage, ParamDescriptor


class Grain(PipelineStage):
    stage_name = "Grain"

    @property
    def name(self) -> str:
        return self.stage_name

    def get_params(self) -> list[ParamDescriptor]:
        return [
            ParamDescriptor("amount",     "Amount",     0,  100, 20, 1, 0),
            ParamDescriptor("monochrome", "Monochrome", 0,  1,   1,  1, 0),
        ]

    def process(self, frame: np.ndarray, context: dict) -> np.ndarray:
        amount = int(self._params["amount"])
        if amount == 0:
            return frame

        h, w = frame.shape[:2]
        mono = int(self._params["monochrome"])

        if mono or frame.ndim == 2:
            noise = np.random.normal(0, amount, (h, w)).astype(np.int16)
            if frame.ndim == 3:
                noise = noise[:, :, np.newaxis]
        else:
            noise = np.random.normal(0, amount, frame.shape).astype(np.int16)

        return np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
