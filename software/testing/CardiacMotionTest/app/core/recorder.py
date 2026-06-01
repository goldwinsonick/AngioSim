import csv
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


class DataRecorder:
    """Writes tracking data to CSV. Not a thread — called from UI thread."""

    COLUMNS = [
        "timestamp_s",
        "displacement_mm",
        "heart_area_px",
        "pump_duty",
        "valve_duty",
        "bpm_estimate",
    ]

    def __init__(self):
        self._file = None
        self._writer = None
        self._path: Path | None = None

    def start(self, output_path: Path) -> None:
        self._path = output_path
        self._file = open(output_path, "w", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=self.COLUMNS)
        self._writer.writeheader()

    def stop(self) -> None:
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None
            self._writer = None

    def record(
        self,
        timestamp: float,
        displacement_mm: float | None,
        heart_area_px: int,
        pump_duty: int,
        valve_duty: int,
        bpm_estimate: float | None,
    ) -> None:
        if self._writer is None:
            return
        self._writer.writerow({
            "timestamp_s": f"{timestamp:.4f}",
            "displacement_mm": f"{displacement_mm:.4f}" if displacement_mm is not None else "",
            "heart_area_px": heart_area_px,
            "pump_duty": pump_duty,
            "valve_duty": valve_duty,
            "bpm_estimate": f"{bpm_estimate:.1f}" if bpm_estimate is not None else "",
        })

    @property
    def is_recording(self) -> bool:
        return self._file is not None

    @property
    def last_path(self) -> Path | None:
        return self._path

    @staticmethod
    def generate_graph(csv_path: Path, output_path: Path | None = None) -> None:
        times, displacements, bpms = [], [], []
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            t0 = None
            for row in reader:
                try:
                    t = float(row["timestamp_s"])
                    if t0 is None:
                        t0 = t
                    times.append(t - t0)
                    d = row["displacement_mm"]
                    displacements.append(float(d) if d else None)
                    b = row["bpm_estimate"]
                    bpms.append(float(b) if b else None)
                except (ValueError, KeyError):
                    continue

        fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

        # Displacement plot
        valid_t = [t for t, d in zip(times, displacements) if d is not None]
        valid_d = [d for d in displacements if d is not None]
        axes[0].plot(valid_t, valid_d, color="#1f77b4", linewidth=1.0)
        axes[0].axhline(0, color="gray", linewidth=0.5, linestyle="--")
        axes[0].set_ylabel("Displacement (mm)")
        axes[0].set_title("Heart Displacement Over Time")
        axes[0].grid(True, alpha=0.3)

        # BPM plot
        valid_t_b = [t for t, b in zip(times, bpms) if b is not None]
        valid_b = [b for b in bpms if b is not None]
        axes[1].plot(valid_t_b, valid_b, color="#ff7f0e", linewidth=1.0)
        axes[1].set_ylabel("BPM")
        axes[1].set_xlabel("Time (s)")
        axes[1].set_title("Estimated Heart Rate")
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()
        if output_path:
            plt.savefig(output_path, dpi=150)
            plt.close(fig)
        else:
            plt.show()
