from pathlib import Path

import cv2
import numpy as np


class VideoRecorder:
    """Wraps cv2.VideoWriter. Called from the UI thread via frame_ready slot."""

    def __init__(self):
        self._writer: cv2.VideoWriter | None = None
        self._frame_count = 0

    def start(self, output_path: Path, fps: float, frame_size: tuple[int, int]) -> None:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(str(output_path), fourcc, fps, frame_size)
        self._frame_count = 0

    def write_frame(self, frame: np.ndarray) -> None:
        if self._writer is not None and self._writer.isOpened():
            self._writer.write(frame)
            self._frame_count += 1

    def stop(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None

    @property
    def is_recording(self) -> bool:
        return self._writer is not None and self._writer.isOpened()

    @property
    def frame_count(self) -> int:
        return self._frame_count
