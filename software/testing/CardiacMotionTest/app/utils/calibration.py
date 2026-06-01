import math


class Calibration:
    def __init__(self):
        self._px_per_mm: float | None = None

    def set_reference(
        self,
        p1: tuple[int, int],
        p2: tuple[int, int],
        physical_distance_mm: float,
    ) -> None:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist_px = math.hypot(dx, dy)
        if dist_px > 0 and physical_distance_mm > 0:
            self._px_per_mm = dist_px / physical_distance_mm

    def reset(self) -> None:
        self._px_per_mm = None

    @property
    def px_per_mm(self) -> float | None:
        return self._px_per_mm

    @property
    def is_calibrated(self) -> bool:
        return self._px_per_mm is not None

    def px_to_mm(self, pixels: float) -> float | None:
        if self._px_per_mm is None:
            return None
        return pixels / self._px_per_mm

    def mm_to_px(self, mm: float) -> float | None:
        if self._px_per_mm is None:
            return None
        return mm * self._px_per_mm
