from __future__ import annotations
import threading
import time
from collections import deque

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

RESOLUTION_PRESETS: dict[str, tuple[int, int, int]] = {
    "1080p @ 30fps": (1920, 1080, 30),
    "720p @ 60fps":  (1280, 720,  60),
    "480p @ 30fps":  (640,  480,  30),
}


def scan_cameras(max_index: int = 5) -> list[int]:
    available = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
        cap.release()
    return available


class CameraThread(QThread):
    # frame_ready carries NO frame data — caller pulls via get_latest_frame().
    # This prevents the Qt signal queue from flooding when the camera is faster
    # than the main thread's processing speed.
    frame_ready = pyqtSignal()
    fps_updated = pyqtSignal(float)
    error_occurred = pyqtSignal(str)
    position_updated = pyqtSignal(int, int)   # (current_frame, total_frames) — video only

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source_type: str = "camera"
        self._source: int | str = 0
        self._resolution_key: str = "1080p @ 30fps"
        self._running = False
        self._timestamps: deque[float] = deque(maxlen=30)

        self._latest_frame: np.ndarray | None = None
        self._frame_seq: int = 0
        self._frame_lock = threading.Lock()

        self._pause_event = threading.Event()
        self._pause_event.set()           # set = not paused

        # Seek request stored as (frame_num, was_paused_at_request_time).
        # was_paused is captured with the FIRST seek of a drag gesture and
        # preserved on subsequent rapid overwrites, so rapid slider movement
        # cannot flip was_paused to False while the thread hasn't processed yet.
        self._seek_request: tuple[int, bool] | None = None
        self._seek_lock = threading.Lock()

    # ------------------------------------------------------------------
    def configure(self, source_type: str, source: int | str, resolution_key: str) -> None:
        self._source_type = source_type
        self._source = source
        self._resolution_key = resolution_key

    def get_latest_frame(self) -> tuple[np.ndarray, int] | None:
        """Returns (frame_copy, seq_number) or None. seq_number increments each new frame."""
        with self._frame_lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy(), self._frame_seq

    def pause(self) -> None:
        self._pause_event.clear()

    def resume(self) -> None:
        self._pause_event.set()

    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def seek(self, frame_num: int) -> None:
        with self._seek_lock:
            # Preserve was_paused from the first seek of a drag gesture.
            # If a previous seek is still pending, the user was already paused
            # at that point — keep that value so rapid overwrites don't flip it.
            if self._seek_request is not None:
                _, was_paused = self._seek_request
            else:
                was_paused = self.is_paused()
            self._seek_request = (frame_num, was_paused)
        self._pause_event.set()   # wake thread so seek is processed immediately

    def stop(self) -> None:
        self._running = False
        self._pause_event.set()   # unblock any wait()
        self.wait()

    # ------------------------------------------------------------------
    def run(self) -> None:
        self._running = True
        self._timestamps.clear()
        self._pause_event.set()
        with self._frame_lock:
            self._latest_frame = None

        if self._source_type == "image":
            self._run_image()
        elif self._source_type == "video":
            self._run_video()
        else:
            self._run_camera()

    def _run_image(self) -> None:
        frame = cv2.imread(str(self._source))
        if frame is None:
            self.error_occurred.emit(f"Cannot load image: {self._source}")
            return
        self._push_frame(frame)
        while self._running:
            self.msleep(100)

    def _run_video(self) -> None:
        cap = cv2.VideoCapture(str(self._source))
        if not cap.isOpened():
            self.error_occurred.emit(f"Cannot open video: {self._source}")
            return

        total = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_delay_ms = max(1, int(1000.0 / video_fps))

        try:
            while self._running:
                # Process any pending seek
                with self._seek_lock:
                    seek_req, self._seek_request = self._seek_request, None
                if seek_req is not None:
                    frame_num, was_paused = seek_req
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                    ret, frame = cap.read()
                    if ret:
                        self._push_frame(frame)
                        self.position_updated.emit(int(cap.get(cv2.CAP_PROP_POS_FRAMES)), total)
                    if was_paused:
                        self._pause_event.clear()   # re-pause after preview
                    continue

                # Block while paused. Use continue so that after waking
                # (whether from resume() or seek()) we re-enter the top of
                # the loop and handle any pending seek before reading a frame.
                if not self._pause_event.is_set():
                    self._pause_event.wait()
                    continue

                if not self._running:
                    break

                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.position_updated.emit(0, total)
                    continue

                self.position_updated.emit(int(cap.get(cv2.CAP_PROP_POS_FRAMES)), total)
                self._push_frame(frame)
                self.msleep(frame_delay_ms)
        finally:
            cap.release()

    def _run_camera(self) -> None:
        w, h, fps_target = RESOLUTION_PRESETS.get(
            self._resolution_key, (1920, 1080, 30)
        )
        cap = cv2.VideoCapture(int(self._source))
        if not cap.isOpened():
            self.error_occurred.emit(f"Cannot open camera index {self._source}")
            return

        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        cap.set(cv2.CAP_PROP_FPS, fps_target)

        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    self.error_occurred.emit("Camera read failed")
                    break
                self._push_frame(frame)
        finally:
            cap.release()

    def _push_frame(self, frame: np.ndarray) -> None:
        with self._frame_lock:
            self._latest_frame = frame
            self._frame_seq += 1
        now = time.monotonic()
        self._timestamps.append(now)
        if len(self._timestamps) >= 2:
            elapsed = self._timestamps[-1] - self._timestamps[0]
            fps = (len(self._timestamps) - 1) / elapsed if elapsed > 0 else 0.0
            self.fps_updated.emit(fps)
        self.frame_ready.emit()


class CameraManager:
    def __init__(self, parent=None) -> None:
        self._thread = CameraThread(parent)

    @property
    def thread(self) -> CameraThread:
        return self._thread

    def start(self, source_type: str, source: int | str, resolution_key: str) -> None:
        if self._thread.isRunning():
            self._thread.stop()
        self._thread.configure(source_type, source, resolution_key)
        self._thread.start()

    def stop(self) -> None:
        self._thread.stop()

    def is_running(self) -> bool:
        return self._thread.isRunning()
