from __future__ import annotations
import numpy as np
import cv2
from core.pipeline import PipelineStage, ParamDescriptor


class FisheyeCorrection(PipelineStage):
    stage_name = "FisheyeCorrection"

    def __init__(self) -> None:
        super().__init__()
        self._map_cache: tuple | None = None   # (map1, map2, key)

    @property
    def name(self) -> str:
        return self.stage_name

    def get_params(self) -> list[ParamDescriptor]:
        return [
            ParamDescriptor("k1",   "K1",   -2.0, 2.0, 0.0, 0.01, 3),
            ParamDescriptor("k2",   "K2",   -2.0, 2.0, 0.0, 0.01, 3),
            ParamDescriptor("k3",   "K3",   -2.0, 2.0, 0.0, 0.01, 3),
            ParamDescriptor("k4",   "K4",   -2.0, 2.0, 0.0, 0.01, 3),
            ParamDescriptor("zoom", "Zoom",  0.1, 3.0, 1.0, 0.01, 2),
        ]

    def set_param_value(self, name: str, value: float) -> None:
        super().set_param_value(name, value)
        self._map_cache = None   # invalidate on any param change

    def process(self, frame: np.ndarray, context: dict) -> np.ndarray:
        k1 = self._params["k1"]
        k2 = self._params["k2"]
        k3 = self._params["k3"]
        k4 = self._params["k4"]
        zoom = self._params["zoom"]

        if k1 == 0.0 and k2 == 0.0 and k3 == 0.0 and k4 == 0.0:
            return frame

        h, w = frame.shape[:2]
        cache_key = (w, h, k1, k2, k3, k4, zoom)

        if self._map_cache is None or self._map_cache[2] != cache_key:
            f = max(w, h) * zoom
            K = np.array([[f, 0, w / 2],
                          [0, f, h / 2],
                          [0, 0, 1]], dtype=np.float64)
            D = np.array([[k1], [k2], [k3], [k4]], dtype=np.float64)
            new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
                K, D, (w, h), np.eye(3), balance=0.0
            )
            map1, map2 = cv2.fisheye.initUndistortRectifyMap(
                K, D, np.eye(3), new_K, (w, h), cv2.CV_16SC2
            )
            self._map_cache = (map1, map2, cache_key)

        map1, map2, _ = self._map_cache
        return cv2.remap(frame, map1, map2, interpolation=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT)
