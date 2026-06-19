from __future__ import annotations
import numpy as np
from core.pipeline import PipelineStage, ParamDescriptor


class Crop(PipelineStage):
    stage_name = "Crop"

    @property
    def name(self) -> str:
        return self.stage_name

    def get_params(self) -> list[ParamDescriptor]:
        return [
            ParamDescriptor("x", "X (px)",      0, 4096, 0,    1, 0),
            ParamDescriptor("y", "Y (px)",      0, 4096, 0,    1, 0),
            ParamDescriptor("w", "Width (px)",  1, 4096, 4096, 1, 0),
            ParamDescriptor("h", "Height (px)", 1, 4096, 4096, 1, 0),
        ]

    def process(self, frame: np.ndarray, context: dict) -> np.ndarray:
        fh, fw = frame.shape[:2]
        x = max(0, min(int(self._params["x"]), fw - 1))
        y = max(0, min(int(self._params["y"]), fh - 1))
        w = max(1, min(int(self._params["w"]), fw - x))
        h = max(1, min(int(self._params["h"]), fh - y))
        return frame[y:y + h, x:x + w]
