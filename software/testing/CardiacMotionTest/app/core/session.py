import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Session:
    label: str
    notes: str
    start_time: str        # ISO format
    fps: float
    frame_width: int
    frame_height: int
    total_frames: int
    pwm_settings: dict = field(default_factory=dict)
    # pwm_settings schema:
    # {"1": {"freq_hz": 20000, "duty": 0}, "2": {...}, ...}

    def save(self, folder: Path) -> None:
        (folder / "session.json").write_text(
            json.dumps(asdict(self), indent=2), encoding="utf-8"
        )

    @staticmethod
    def load(folder: Path) -> "Session":
        data = json.loads((folder / "session.json").read_text(encoding="utf-8"))
        return Session(**data)
