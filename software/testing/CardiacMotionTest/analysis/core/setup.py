import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AnalysisSetup:
    video_name: str
    frame_width: int
    frame_height: int
    markers: list[list[int]]                       # [[x, y], ...] positions AT the rest frame
    rest_frame_index: int                            # frame where markers were placed (= rest reference)
    sync_offset_s: float = 0.0                        # aligns this video's t=0 with a shared reference

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @staticmethod
    def load(path: Path) -> "AnalysisSetup":
        data = json.loads(path.read_text(encoding="utf-8"))
        return AnalysisSetup(**data)

    @staticmethod
    def setup_path_for(video_path: Path) -> Path:
        return video_path.with_name(f"{video_path.stem}_setup.json")
