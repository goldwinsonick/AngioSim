import time

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal


class CameraThread(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    frame_size_ready = pyqtSignal(int, int, float)  # width, height, measured_fps
    camera_error = pyqtSignal(str)

    def __init__(self, camera_index: int = 0, target_fps: int = 30,
                 width: int = 1280, height: int = 720, parent=None):
        super().__init__(parent)
        self._camera_index = camera_index
        self._target_fps = target_fps
        self._width = width
        self._height = height
        self._running = False
        self._pending = False   # frame-drop flag

    def set_resolution(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def start_capture(self, camera_index: int | None = None) -> None:
        if camera_index is not None:
            self._camera_index = camera_index
        self._running = True
        self.start()

    def stop_capture(self) -> None:
        self._running = False
        self.wait(3000)

    # Called from UI thread when it finishes displaying a frame
    def mark_displayed(self) -> None:
        self._pending = False

    def run(self) -> None:
        cap = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self._camera_index)
        if not cap.isOpened():
            self.camera_error.emit(f"Cannot open camera {self._camera_index}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        cap.set(cv2.CAP_PROP_FPS, self._target_fps)
        # MJPEG gives much higher frame rates over USB than raw YUY2
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

        # Warm up: discard first few frames (camera AGC settling)
        for _ in range(5):
            cap.read()

        # Measure actual FPS over 20 frames
        t0 = time.monotonic()
        for _ in range(20):
            cap.read()
        measured_fps = 20.0 / max(time.monotonic() - t0, 0.001)
        measured_fps = round(measured_fps, 2)

        # Emit actual camera resolution (may differ from requested)
        ok, probe = cap.read()
        if not ok:
            self.camera_error.emit("Camera opened but cannot read frames")
            cap.release()
            return
        h, w = probe.shape[:2]
        self.frame_size_ready.emit(w, h, measured_fps)

        frame_interval = 1.0 / measured_fps
        self._pending = False

        # Emit the probe frame first
        self._pending = True
        self.frame_ready.emit(probe)

        while self._running:
            t_start = time.monotonic()

            ok, frame = cap.read()
            if not ok:
                self.camera_error.emit("Failed to read frame")
                break

            # Drop frame if UI thread hasn't finished with the previous one
            if not self._pending:
                self._pending = True
                self.frame_ready.emit(frame)

            elapsed = time.monotonic() - t_start
            sleep_s = frame_interval - elapsed
            if sleep_s > 0.001:
                time.sleep(sleep_s)

        cap.release()
