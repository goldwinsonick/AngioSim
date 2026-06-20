from __future__ import annotations
import numpy as np
import cv2
from core.pipeline import PipelineStage, ParamDescriptor


class Transform(PipelineStage):
    """Rotate and/or zoom the image around a configurable center point."""

    stage_name = "Transform"

    @property
    def name(self) -> str:
        return self.stage_name

    def get_params(self) -> list[ParamDescriptor]:
        return [
            ParamDescriptor("angle",     "Angle (deg)",  -180, 180, 0.0, 0.5,  1),
            ParamDescriptor("zoom",      "Zoom",          0.1, 5.0, 1.0, 0.01, 2),
            ParamDescriptor("center_x",  "Center X",      0.0, 1.0, 0.5, 0.01, 2),
            ParamDescriptor("center_y",  "Center Y",      0.0, 1.0, 0.5, 0.01, 2),
            ParamDescriptor("border_val","Border",         0,   255, 0,   1,    0),
        ]

    def process(self, frame: np.ndarray, context: dict) -> np.ndarray:
        h, w = frame.shape[:2]
        angle     = self._params["angle"]
        zoom      = self._params["zoom"]
        cx        = self._params["center_x"] * w
        cy        = self._params["center_y"] * h
        border    = int(self._params["border_val"])

        M = cv2.getRotationMatrix2D((cx, cy), angle, zoom)
        return cv2.warpAffine(
            frame, M, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(border, border, border),
        )
