import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class LensCalibration:
    """
    Manually-tuned radial lens-distortion correction for one camera/source.

    Saved once per camera (e.g. "top_lens.json") and auto-applied to every
    video recorded with that camera — distortion is a property of the lens,
    not of an individual recording, so it never needs to be redone per video.
    """

    label: str
    frame_width: int
    frame_height: int
    k1: float = 0.0
    k2: float = 0.0
    p1: float = 0.0
    p2: float = 0.0
    focal_scale: float = 1.0   # fx = fy = focal_scale * frame_width

    @property
    def camera_matrix(self) -> np.ndarray:
        f = self.focal_scale * self.frame_width
        return np.array(
            [[f, 0.0, self.frame_width / 2.0],
             [0.0, f, self.frame_height / 2.0],
             [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )

    @property
    def dist_coeffs(self) -> np.ndarray:
        return np.array([self.k1, self.k2, self.p1, self.p2], dtype=np.float64)

    def undistort_frame(self, frame: np.ndarray) -> np.ndarray:
        return cv2.undistort(frame, self.camera_matrix, self.dist_coeffs)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @staticmethod
    def load(path: Path) -> "LensCalibration":
        data = json.loads(path.read_text(encoding="utf-8"))
        return LensCalibration(**data)

    @staticmethod
    def path_for(label: str, calibration_dir: Path) -> Path:
        return calibration_dir / f"{label}_lens.json"

    @staticmethod
    def source_label_for(video_path: Path) -> str:
        """Infers the shared calibration label ("top"/"side") from the data folder layout."""
        parts = [p.lower() for p in video_path.parts]
        if "top_recording" in parts:
            return "top"
        if "side_recording" in parts:
            return "side"
        return "default"
