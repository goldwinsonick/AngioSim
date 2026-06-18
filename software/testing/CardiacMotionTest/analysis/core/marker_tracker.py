import math

import cv2
import numpy as np


class MarkerTracker:
    """
    Tracks multiple point markers across video frames using
    Lucas-Kanade sparse optical flow.
    """

    LK_PARAMS = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    def __init__(self):
        self._points: np.ndarray | None = None  # (N, 1, 2) float32
        self._prev_gray: np.ndarray | None = None
        self._n: int = 0

    def initialize(self, frame: np.ndarray, points: list[tuple[int, int]]) -> None:
        self._prev_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self._points = np.array(points, dtype=np.float32).reshape(-1, 1, 2)
        self._n = len(points)

    def track(self, frame: np.ndarray) -> list[tuple[float, float]] | None:
        """
        Run LK optical flow. Returns list of (x, y) per marker,
        or None if any marker is lost.
        """
        if self._points is None or self._prev_gray is None:
            return None

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        new_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            self._prev_gray, gray, self._points, None, **self.LK_PARAMS
        )
        self._prev_gray = gray

        if new_pts is None or status is None:
            return None
        if status.sum() < self._n:
            return None  # at least one marker lost

        self._points = new_pts
        return [(float(p[0][0]), float(p[0][1])) for p in new_pts]

    def reset(self) -> None:
        self._points = None
        self._prev_gray = None
        self._n = 0

    @property
    def n_markers(self) -> int:
        return self._n

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    @staticmethod
    def draw_markers(
        frame: np.ndarray,
        positions: list[tuple[float, float]],
        rest_positions: list[tuple[float, float]] | None = None,
    ) -> np.ndarray:
        """Draw colored numbered circles, and each marker's pixel offset from rest."""
        colors = [
            (0, 255, 100), (0, 150, 255), (255, 80, 80),
            (255, 220, 0), (200, 0, 255),
        ]
        out = frame.copy()
        for i, (x, y) in enumerate(positions):
            color = colors[i % len(colors)]
            cx, cy = int(x), int(y)
            cv2.circle(out, (cx, cy), 8, color, -1)
            cv2.circle(out, (cx, cy), 9, (0, 0, 0), 1)
            cv2.putText(out, str(i), (cx + 10, cy - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

            if rest_positions is not None and i < len(rest_positions):
                rx, ry = rest_positions[i]
                rcx, rcy = int(rx), int(ry)
                cv2.drawMarker(out, (rcx, rcy), color, cv2.MARKER_CROSS, 14, 1)
                cv2.line(out, (rcx, rcy), (cx, cy), (200, 200, 200), 1, cv2.LINE_AA)
                disp_px = math.hypot(x - rx, y - ry)
                cv2.putText(out, f"{disp_px:+.1f}px", (cx + 10, cy + 14),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        return out
