from __future__ import annotations
import time
import numpy as np
from core.pipeline import Pipeline


class FluoroscopyImageProcessor:
    def __init__(self) -> None:
        self.pipeline = Pipeline()

    def process(self, frame: np.ndarray) -> tuple[list[np.ndarray], float]:
        """
        Run frame through the pipeline.
        Returns (stage_frames, elapsed_ms) where stage_frames[0] is raw.
        """
        t0 = time.perf_counter()
        stage_frames = self.pipeline.process(frame)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return stage_frames, elapsed_ms
