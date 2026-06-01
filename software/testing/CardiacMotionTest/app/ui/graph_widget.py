import time
from collections import deque

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QTimer


class GraphWidget(pg.PlotWidget):
    """Scrolling real-time plot of heart displacement vs. time."""

    def __init__(self, window_seconds: int = 10, parent=None):
        super().__init__(parent)
        self._window_s = window_seconds
        self._times: deque[float] = deque()
        self._values: deque[float] = deque()
        self._t0: float | None = None

        self._dirty = False
        self._last_draw = 0.0

        # Style
        self.setBackground("#1a1a2e")
        self.setTitle("Heart Displacement", color="#eee", size="10pt")
        self.setLabel("left", "Displacement", units="mm")
        self.setLabel("bottom", "Time", units="s")
        self.showGrid(x=True, y=True, alpha=0.2)
        self.addLegend()

        pen = pg.mkPen(color="#00d4ff", width=1.5)
        self._curve = self.plot([], [], pen=pen, name="displacement")

        self.setYRange(-6, 6)

        # Zero reference line
        self.addLine(y=0, pen=pg.mkPen("#555", width=1, style=pg.QtCore.Qt.PenStyle.DashLine))

        # Redraw timer at 10Hz
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._redraw_if_dirty)
        self._timer.start(100)

    def update_data(self, timestamp: float, displacement_mm: float) -> None:
        if self._t0 is None:
            self._t0 = timestamp
        t_rel = timestamp - self._t0
        self._times.append(t_rel)
        self._values.append(displacement_mm)

        # Prune old data beyond window
        cutoff = t_rel - self._window_s
        while self._times and self._times[0] < cutoff:
            self._times.popleft()
            self._values.popleft()

        self._dirty = True

    def clear_data(self) -> None:
        self._times.clear()
        self._values.clear()
        self._t0 = None
        self._curve.setData([], [])

    def _redraw_if_dirty(self) -> None:
        if not self._dirty or not self._times:
            return
        self._dirty = False
        xs = np.array(self._times)
        ys = np.array(self._values)
        self._curve.setData(xs, ys)
        if len(xs) > 0:
            x_max = xs[-1]
            self.setXRange(max(0, x_max - self._window_s), x_max + 0.2, padding=0)
