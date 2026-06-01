import time
from collections import deque

import cv2
import numpy as np
import scipy.signal


class HeartTracker:
    """
    Stateful heart tracker. Called from CameraThread on every frame.
    Measures heart displacement along a user-defined line and estimates BPM.
    """

    def __init__(self):
        self._roi: tuple[int, int, int, int] | None = None  # (x, y, w, h)
        self._line_p1: tuple[int, int] | None = None
        self._line_p2: tuple[int, int] | None = None

        self._lower_thresh = 160
        self._upper_thresh = 255
        self._morph_open_k = 5
        self._morph_close_k = 7

        self._px_per_mm: float | None = None
        self._reference_center: float | None = None

        # BPM estimation buffer: deque of (timestamp, displacement_px)
        self._history: deque[tuple[float, float]] = deque(maxlen=600)
        self._bpm_smooth: float | None = None
        self._show_overlay = True

    # ------------------------------------------------------------------
    # Configuration setters (called from UI thread via CameraThread proxy)
    # ------------------------------------------------------------------

    def set_roi(self, roi: tuple[int, int, int, int] | None) -> None:
        self._roi = roi
        self._reference_center = None

    def set_line(self, p1: tuple[int, int], p2: tuple[int, int]) -> None:
        self._line_p1 = p1
        self._line_p2 = p2
        self._reference_center = None
        self._history.clear()
        self._bpm_smooth = None

    def set_thresholds(self, lower: int, upper: int) -> None:
        self._lower_thresh = lower
        self._upper_thresh = upper

    def set_morph_kernel_size(self, open_k: int, close_k: int) -> None:
        self._morph_open_k = open_k
        self._morph_close_k = close_k

    def set_calibration(self, px_per_mm: float | None) -> None:
        self._px_per_mm = px_per_mm

    def set_show_overlay(self, show: bool) -> None:
        self._show_overlay = show

    def reset_reference(self) -> None:
        self._reference_center = None
        self._history.clear()
        self._bpm_smooth = None

    # ------------------------------------------------------------------
    # Main processing — called from camera thread
    # ------------------------------------------------------------------

    def process(self, frame: np.ndarray) -> dict:
        timestamp = time.monotonic()
        annotated = frame.copy()

        mask = self._segment_heart(frame)
        area = int(np.sum(mask > 0))

        displacement_px = 0.0
        displacement_mm = None
        top_px = bottom_px = None

        if self._line_p1 and self._line_p2:
            top_px, bottom_px, displacement_px = self._measure_along_line(mask)
            if self._px_per_mm is not None and displacement_px is not None:
                displacement_mm = displacement_px / self._px_per_mm

        if displacement_px is not None:
            self._history.append((timestamp, displacement_px))

        bpm = self._estimate_bpm(timestamp)

        if self._show_overlay:
            annotated = self._draw_overlay(annotated, mask, top_px, bottom_px, displacement_px, displacement_mm, bpm)

        return {
            "timestamp": timestamp,
            "displacement_px": displacement_px if displacement_px is not None else 0.0,
            "displacement_mm": displacement_mm,
            "heart_area_px": area,
            "bpm_estimate": bpm,
            "annotated_frame": annotated,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_roi_mask(self, frame: np.ndarray) -> np.ndarray:
        if self._roi is None:
            return frame
        x, y, w, h = self._roi
        masked = np.zeros_like(frame)
        masked[y:y+h, x:x+w] = frame[y:y+h, x:x+w]
        return masked

    def _segment_heart(self, frame: np.ndarray) -> np.ndarray:
        masked_frame = self._apply_roi_mask(frame)
        gray = cv2.cvtColor(masked_frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        binary = cv2.inRange(blurred, self._lower_thresh, self._upper_thresh)

        open_k = max(1, self._morph_open_k | 1)  # ensure odd
        close_k = max(1, self._morph_close_k | 1)
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_k, open_k))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_k, close_k))
        opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open)
        closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel_close)

        # Keep only the largest contour to exclude reflections/noise
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return np.zeros_like(closed)
        largest = max(contours, key=cv2.contourArea)
        final_mask = np.zeros_like(closed)
        cv2.drawContours(final_mask, [largest], -1, 255, thickness=cv2.FILLED)
        return final_mask

    def _measure_along_line(
        self, mask: np.ndarray
    ) -> tuple[float | None, float | None, float | None]:
        if self._line_p1 is None or self._line_p2 is None:
            return None, None, None

        p1 = self._line_p1
        p2 = self._line_p2
        n_samples = 500
        xs = np.linspace(p1[0], p2[0], n_samples).astype(int)
        ys = np.linspace(p1[1], p2[1], n_samples).astype(int)

        h, w = mask.shape
        xs = np.clip(xs, 0, w - 1)
        ys = np.clip(ys, 0, h - 1)

        samples = mask[ys, xs]
        hit_indices = np.where(samples == 255)[0]

        if len(hit_indices) < 2:
            return None, None, None

        seg_len = float(np.hypot(p2[0] - p1[0], p2[1] - p1[1]))
        top_px = float(hit_indices[0]) * seg_len / n_samples
        bottom_px = float(hit_indices[-1]) * seg_len / n_samples
        center = (top_px + bottom_px) / 2.0

        if self._reference_center is None:
            self._reference_center = center

        displacement_px = center - self._reference_center
        return top_px, bottom_px, displacement_px

    def _estimate_bpm(self, current_time: float) -> float | None:
        window_s = 10.0
        min_samples = 90  # ~3s at 30fps

        cutoff = current_time - window_s
        recent = [(t, d) for t, d in self._history if t >= cutoff]
        if len(recent) < min_samples:
            return None

        times = np.array([r[0] for r in recent])
        displacements = np.array([r[1] for r in recent])

        # Resample to uniform grid at 30Hz
        fps = 30.0
        t_uniform = np.linspace(times[0], times[-1], int((times[-1] - times[0]) * fps))
        if len(t_uniform) < 10:
            return None
        d_uniform = np.interp(t_uniform, times, displacements)

        # Minimum peak distance: at 120 BPM => 0.5s => 15 samples at 30fps
        min_dist = int(fps * 0.4)
        peaks, _ = scipy.signal.find_peaks(d_uniform, prominence=1.0, distance=min_dist)
        if len(peaks) < 2:
            return None

        window_duration = times[-1] - times[0]
        bpm_raw = (len(peaks) / window_duration) * 60.0

        if self._bpm_smooth is None:
            self._bpm_smooth = bpm_raw
        else:
            self._bpm_smooth = 0.7 * self._bpm_smooth + 0.3 * bpm_raw

        return round(self._bpm_smooth, 1)

    def _draw_overlay(
        self,
        frame: np.ndarray,
        mask: np.ndarray,
        top_px: float | None,
        bottom_px: float | None,
        displacement_px: float | None,
        displacement_mm: float | None,
        bpm: float | None,
    ) -> np.ndarray:
        out = frame.copy()

        # Draw ROI rectangle
        if self._roi is not None:
            x, y, w, h = self._roi
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 200, 255), 1)

        # Draw heart mask outline in green
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(out, contours, -1, (0, 255, 0), 1)

        # Draw measurement line
        if self._line_p1 and self._line_p2:
            cv2.line(out, self._line_p1, self._line_p2, (255, 100, 0), 1)

            # Mark edge contact points on the line
            if top_px is not None and bottom_px is not None:
                p1 = self._line_p1
                p2 = self._line_p2
                seg_len = np.hypot(p2[0] - p1[0], p2[1] - p1[1])
                if seg_len > 0:
                    dx = (p2[0] - p1[0]) / seg_len
                    dy = (p2[1] - p1[1]) / seg_len
                    pt_top = (int(p1[0] + dx * top_px), int(p1[1] + dy * top_px))
                    pt_bot = (int(p1[0] + dx * bottom_px), int(p1[1] + dy * bottom_px))
                    cv2.circle(out, pt_top, 4, (0, 255, 255), -1)
                    cv2.circle(out, pt_bot, 4, (0, 255, 255), -1)

        # HUD text
        font = cv2.FONT_HERSHEY_SIMPLEX
        y_txt = 20
        if displacement_mm is not None:
            cv2.putText(out, f"Disp: {displacement_mm:+.2f} mm", (8, y_txt),
                        font, 0.55, (0, 255, 100), 1, cv2.LINE_AA)
        elif displacement_px is not None:
            cv2.putText(out, f"Disp: {displacement_px:+.1f} px", (8, y_txt),
                        font, 0.55, (0, 255, 100), 1, cv2.LINE_AA)
        y_txt += 22
        if bpm is not None:
            cv2.putText(out, f"BPM:  {bpm:.1f}", (8, y_txt),
                        font, 0.55, (0, 255, 100), 1, cv2.LINE_AA)

        return out
