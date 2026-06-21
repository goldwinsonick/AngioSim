from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QDialog, QDialogButtonBox, QLabel, QComboBox,
)
from core.pipeline import Pipeline, PipelineStage
from core.stages import STAGE_REGISTRY


class _AddStageDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Stage")
        self._combo = QComboBox()
        self._combo.addItems(sorted(STAGE_REGISTRY.keys()))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select stage to add:"))
        layout.addWidget(self._combo)
        layout.addWidget(buttons)

    def selected_name(self) -> str:
        return self._combo.currentText()


class PipelineEditor(QWidget):
    """
    Displays the pipeline stage list with checkboxes.
    Signals:
      pipeline_changed — emitted whenever stages are added/removed/moved/toggled
      stage_selected(int) — emitted when user clicks a stage row (-1 = none)
    """

    pipeline_changed = pyqtSignal()
    stage_selected = pyqtSignal(int)

    def __init__(self, pipeline: Pipeline, parent=None) -> None:
        super().__init__(parent)
        self._pipeline = pipeline

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.itemChanged.connect(self._on_item_changed)

        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_stage)
        btn_remove = QPushButton("Remove")
        btn_remove.clicked.connect(self._remove_stage)
        btn_up = QPushButton("↑")
        btn_up.setFixedWidth(32)
        btn_up.clicked.connect(self._move_up)
        btn_dn = QPushButton("↓")
        btn_dn.setFixedWidth(32)
        btn_dn.clicked.connect(self._move_down)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addStretch()
        btn_row.addWidget(btn_up)
        btn_row.addWidget(btn_dn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(btn_row)
        layout.addWidget(self._list)

        self._last_timings: list[float] = []
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for i, stage in enumerate(self._pipeline.stages):
            ms = self._last_timings[i] if i < len(self._last_timings) else None
            label = f"{stage.name}  {ms:.1f}ms" if ms is not None and ms > 0 else stage.name
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if stage.enabled else Qt.CheckState.Unchecked
            )
            self._list.addItem(item)
        self._list.blockSignals(False)

    def update_timings(self, timings: list[float]) -> None:
        self._last_timings = timings
        self._list.blockSignals(True)
        for i, ms in enumerate(timings):
            item = self._list.item(i)
            if item is None:
                break
            stage_name = self._pipeline.stages[i].name if i < len(self._pipeline.stages) else ""
            item.setText(f"{stage_name}  {ms:.1f}ms" if ms > 0 else stage_name)
        self._list.blockSignals(False)

    def stage_names_for_display(self) -> list[str]:
        """Returns display names for DualView dropdowns: Raw + one per stage."""
        names = ["Raw"]
        for stage in self._pipeline.stages:
            names.append(stage.name)
        return names

    # ------------------------------------------------------------------
    def _add_stage(self) -> None:
        dlg = _AddStageDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name = dlg.selected_name()
        cls = STAGE_REGISTRY.get(name)
        if cls is None:
            return
        self._pipeline.add_stage(cls())
        self.refresh()
        self.pipeline_changed.emit()

    def _remove_stage(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        self._pipeline.remove_stage(row)
        self.refresh()
        self.stage_selected.emit(-1)
        self.pipeline_changed.emit()

    def _move_up(self) -> None:
        row = self._list.currentRow()
        if row <= 0:
            return
        self._pipeline.move_stage(row, row - 1)
        self.refresh()
        self._list.setCurrentRow(row - 1)
        self.pipeline_changed.emit()

    def _move_down(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= self._list.count() - 1:
            return
        self._pipeline.move_stage(row, row + 1)
        self.refresh()
        self._list.setCurrentRow(row + 1)
        self.pipeline_changed.emit()

    def _on_row_changed(self, row: int) -> None:
        self.stage_selected.emit(row)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        row = self._list.row(item)
        stages = self._pipeline.stages
        if 0 <= row < len(stages):
            stages[row].enabled = (item.checkState() == Qt.CheckState.Checked)
            self.pipeline_changed.emit()
