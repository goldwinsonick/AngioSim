import time

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from core.tracker import HeartTracker


class CameraThread(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    tracking_result = pyqtSignal(dict)
    camera_error = pyqtSignal(str)

    def __init__(self, camera_index: int = 0, fps: int = 30, parent=None):
        super().__init__(parent)
        self._camera_index = camera_index
        self._target_fps = fps
        self._running = False
        self._tracker = HeartTracker()

    # ------------------------------------------------------------------
    # Tracker proxy — called from UI thread, safe because tracker state
    # is only read inside run() which checks _running flag.
    # ------------------------------------------------------------------

    def set_roi(self, roi: tuple[int, int, int, int] | None) -> None:
        self._tracker.set_roi(roi)

    def set_line(self, p1: tuple[int, int], p2: tuple[int, int]) -> None:
        self._tracker.set_line(p1, p2)

    def set_thresholds(self, lower: int, upper: int) -> None:
        self._tracker.set_thresholds(lower, upper)

    def set_morph_kernel_size(self, open_k: int, close_k: int) -> None:
        self._tracker.set_morph_kernel_size(open_k, close_k)

    def set_calibration(self, px_per_mm: float | None) -> None:
        self._tracker.set_calibration(px_per_mm)

    def set_show_overlay(self, show: bool) -> None:
        self._tracker.set_show_overlay(show)

    def reset_reference(self) -> None:
        self._tracker.reset_reference()

    @property
    def tracker(self) -> HeartTracker:
        return self._tracker

    # ------------------------------------------------------------------
    # Thread control
    # ------------------------------------------------------------------

    def start_capture(self, camera_index: int | None = None) -> None:
        if camera_index is not None:
            self._camera_index = camera_index
        self._running = True
        self.start()

    def stop_capture(self) -> None:
        self._running = False
        self.wait(3000)

    # ------------------------------------------------------------------
    # QThread.run
    # ------------------------------------------------------------------

    def run(self) -> None:
        # CAP_DSHOW is fastest on Windows for UVC cameras
        cap = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            # Fallback without backend hint
            cap = cv2.VideoCapture(self._camera_index)
        if not cap.isOpened():
            self.camera_error.emit(f"Cannot open camera {self._camera_index}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FPS, self._target_fps)

        frame_interval = 1.0 / self._target_fps

        while self._running:
            t_start = time.monotonic()

            ok, frame = cap.read()
            if not ok:
                self.camera_error.emit("Failed to read frame")
                break

            result = self._tracker.process(frame)
            self.frame_ready.emit(result["annotated_frame"])
            self.tracking_result.emit(result)

            elapsed = time.monotonic() - t_start
            sleep_s = frame_interval - elapsed
            if sleep_s > 0:
                time.sleep(sleep_s)

        cap.release()
