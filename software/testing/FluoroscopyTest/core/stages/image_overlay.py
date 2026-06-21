from __future__ import annotations
from pathlib import Path
from typing import Any

import numpy as np
import cv2
from core.pipeline import PipelineStage, ParamDescriptor

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "overlays"


class ImageOverlay(PipelineStage):
    stage_name = "ImageOverlay"

    def __init__(self) -> None:
        super().__init__()
        self._path: str = str(ASSETS_DIR / "rib_overlay.png")
        self._cached_path: str = ""
        self._cached_overlay: np.ndarray | None = None   # BGRA, original size
        self._blend_cache: tuple | None = None            # (ov_premult, inv_alpha, dst_rect, key)

    @property
    def name(self) -> str:
        return self.stage_name

    def get_params(self) -> list[ParamDescriptor]:
        return [
            ParamDescriptor("opacity", "Opacity", 0.0, 1.0, 0.5, 0.01, 2),
            ParamDescriptor("x",       "X (px)",  -4096, 4096, 0.0, 1.0, 0),
            ParamDescriptor("y",       "Y (px)",  -4096, 4096, 0.0, 1.0, 0),
            ParamDescriptor("scale",   "Scale",   0.1,   5.0,  1.0, 0.01, 2),
        ]

    def get_path_params(self) -> list[tuple[str, str, str]]:
        return [("_path", "Overlay Image", "Images (*.png *.jpg *.jpeg *.bmp *.tiff)")]

    def to_config(self) -> dict[str, Any]:
        cfg = super().to_config()
        cfg["path"] = self._path
        return cfg

    def from_config(self, cfg: dict[str, Any]) -> None:
        super().from_config(cfg)
        self._path = cfg.get("path", self._path)

    def set_param_value(self, name: str, value: float) -> None:
        super().set_param_value(name, value)
        self._blend_cache = None   # any param change invalidates blend cache

    # ------------------------------------------------------------------
    def _load_overlay(self) -> np.ndarray | None:
        if self._path == self._cached_path and self._cached_overlay is not None:
            return self._cached_overlay
        img = cv2.imread(self._path, cv2.IMREAD_UNCHANGED)
        if img is None:
            return None
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        elif img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        self._cached_overlay = img
        self._cached_path    = self._path
        self._blend_cache    = None   # path changed, invalidate blend cache
        return img

    def _build_blend_cache(self, overlay: np.ndarray, fw: int, fh: int) -> bool:
        """Compute and cache the overlay-side of alpha blending.
        Returns False if the overlay doesn't intersect the frame."""
        opacity = self._params["opacity"]
        ox      = int(self._params["x"])
        oy      = int(self._params["y"])
        scale   = self._params["scale"]

        oh, ow = overlay.shape[:2]
        new_w = max(1, int(ow * scale))
        new_h = max(1, int(oh * scale))
        resized = cv2.resize(overlay, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        x1 = max(ox, 0);          y1 = max(oy, 0)
        x2 = min(ox + new_w, fw); y2 = min(oy + new_h, fh)
        if x2 <= x1 or y2 <= y1:
            return False

        src_x1 = x1 - ox;  src_y1 = y1 - oy
        src_x2 = src_x1 + (x2 - x1)
        src_y2 = src_y1 + (y2 - y1)

        roi = resized[src_y1:src_y2, src_x1:src_x2]

        if roi.shape[2] == 4:
            alpha_ch = roi[:, :, 3:4].astype(np.float32) / 255.0 * opacity
        else:
            alpha_ch = np.full((roi.shape[0], roi.shape[1], 1), opacity, dtype=np.float32)

        ov_premult = roi[:, :, :3].astype(np.float32) * alpha_ch
        inv_alpha  = 1.0 - alpha_ch

        cache_key = (self._path, scale, opacity, ox, oy, fw, fh)
        self._blend_cache = (ov_premult, inv_alpha, (y1, y2, x1, x2), cache_key)
        return True

    def process(self, frame: np.ndarray, context: dict) -> np.ndarray:
        overlay = self._load_overlay()
        if overlay is None:
            return frame

        fh, fw = frame.shape[:2]
        cache_key = (self._path, self._params["scale"], self._params["opacity"],
                     int(self._params["x"]), int(self._params["y"]), fw, fh)

        if self._blend_cache is None or self._blend_cache[3] != cache_key:
            if not self._build_blend_cache(overlay, fw, fh):
                return frame

        ov_premult, inv_alpha, (y1, y2, x1, x2), _ = self._blend_cache

        dst = frame.copy()
        dst_roi_f = dst[y1:y2, x1:x2].astype(np.float32)
        blended   = (ov_premult + dst_roi_f * inv_alpha).clip(0, 255).astype(np.uint8)
        dst[y1:y2, x1:x2] = blended
        return dst
