from __future__ import annotations
import numpy as np
import cv2
from core.pipeline import PipelineStage, ParamDescriptor


class Grayscale(PipelineStage):
    stage_name = "Grayscale"

    @property
    def name(self) -> str:
        return self.stage_name

    def get_params(self) -> list[ParamDescriptor]:
        return [
            ParamDescriptor("alpha",  "Contrast",   0.1, 5.0,   1.0, 0.05, 2),
            ParamDescriptor("beta",   "Brightness", -128, 128,   0.0, 1.0,  0),
            ParamDescriptor("invert", "Invert",     0,   1,      0.0, 1.0,  0),
        ]

    def process(self, frame: np.ndarray) -> np.ndarray:
        if frame.ndim == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame.copy()

        alpha = self._params["alpha"]
        beta  = int(self._params["beta"])
        gray = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)

        if int(self._params["invert"]):
            gray = cv2.bitwise_not(gray)

        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
