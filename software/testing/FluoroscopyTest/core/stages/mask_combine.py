from __future__ import annotations
from typing import Any
import numpy as np
import cv2
from core.pipeline import PipelineStage, ParamDescriptor


class MaskCombine(PipelineStage):
    """Combines two named masks from context with a logical operation and
    stores the result under a new name. Never modifies the frame."""

    stage_name = "MaskCombine"

    def __init__(self) -> None:
        super().__init__()
        self._mask_a: str = "mask_a"
        self._mask_b: str = "mask_b"
        self._output: str = "mask_out"

    @property
    def name(self) -> str:
        return self.stage_name

    def get_text_params(self) -> list[tuple[str, str]]:
        return [
            ("_mask_a",  "Mask A"),
            ("_mask_b",  "Mask B"),
            ("_output",  "Output Name"),
        ]

    def get_params(self) -> list[ParamDescriptor]:
        return [
            ParamDescriptor("op", "Op (0=AND 1=OR 2=XOR 3=A-B)", 0, 3, 0, 1, 0),
        ]

    def to_config(self) -> dict[str, Any]:
        cfg = super().to_config()
        cfg["mask_a"] = self._mask_a
        cfg["mask_b"] = self._mask_b
        cfg["output"]  = self._output
        return cfg

    def from_config(self, cfg: dict[str, Any]) -> None:
        super().from_config(cfg)
        self._mask_a = str(cfg.get("mask_a", self._mask_a))
        self._mask_b = str(cfg.get("mask_b", self._mask_b))
        self._output  = str(cfg.get("output",  self._output))

    def process(self, frame: np.ndarray, context: dict) -> np.ndarray:
        a = context.get(self._mask_a)
        b = context.get(self._mask_b)
        if a is None or b is None:
            return frame

        op = int(self._params["op"])
        if op == 0:
            result = cv2.bitwise_and(a, b)
        elif op == 1:
            result = cv2.bitwise_or(a, b)
        elif op == 2:
            result = cv2.bitwise_xor(a, b)
        else:
            result = cv2.subtract(a, b)

        context[self._output] = result
        return frame
