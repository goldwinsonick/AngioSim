from __future__ import annotations
import time
import numpy as np
from core.pipeline import Pipeline


class FluoroscopyImageProcessor:
    def __init__(self) -> None:
        self.pipeline = Pipeline()

    def process(self, frame: np.ndarray) -> tuple[list[np.ndarray], float, list[float]]:
        """Returns (stage_frames, total_ms, stage_timings_ms)."""
        t0 = time.perf_counter()
        stage_frames, stage_timings = self.pipeline.process(frame)
        total_ms = (time.perf_counter() - t0) * 1000.0
        return stage_frames, total_ms, stage_timings
