from __future__ import annotations
import numpy as np
import cv2
from core.pipeline import PipelineStage, ParamDescriptor

_INTERP = [cv2.INTER_LINEAR, cv2.INTER_CUBIC]


class Upsample(PipelineStage):
    """Resize the frame back up after Downsample, either restoring the
    original size or scaling to an explicit target resolution."""

    stage_name = "Upsample"

    @property
    def name(self) -> str:
        return self.stage_name

    def get_params(self) -> list[ParamDescriptor]:
        return [
            ParamDescriptor("mode",   "Mode (0=restore 1=explicit)", 0, 1,    0,    1,    0),
            ParamDescriptor("width",  "Width  (mode=1)",             1, 4096, 1024, 1,    0),
            ParamDescriptor("height", "Height (mode=1)",             1, 4096, 1024, 1,    0),
            ParamDescriptor("interp", "Interp (0=linear 1=cubic)",   0, 1,    0,    1,    0),
        ]

    def process(self, frame: np.ndarray, context: dict) -> np.ndarray:
        mode = int(self._params["mode"])
        interp = _INTERP[int(self._params["interp"])]

        if mode == 0:
            pre = context.get("_pre_downsample_size")
            if pre is None:
                return frame
            tw, th = pre
        else:
            tw = max(1, int(self._params["width"]))
            th = max(1, int(self._params["height"]))

        return cv2.resize(frame, (tw, th), interpolation=interp)
