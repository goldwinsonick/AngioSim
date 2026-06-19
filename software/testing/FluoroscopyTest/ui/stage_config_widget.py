from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QLabel, QSlider, QDoubleSpinBox, QGridLayout,
    QScrollArea, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QFileDialog,
    QLineEdit,
)
from core.pipeline import PipelineStage, ParamDescriptor


class ParamRow(QWidget):
    value_changed = pyqtSignal(str, float)  # (param_name, new_value)

    def __init__(self, desc: ParamDescriptor, parent=None) -> None:
        super().__init__(parent)
        self._desc = desc
        self._updating = False

        label = QLabel(desc.label)
        label.setFixedWidth(60)

        steps = max(1, round((desc.max_val - desc.min_val) / desc.step))
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, steps)
        self._slider.setSingleStep(1)

        self._spinbox = QDoubleSpinBox()
        self._spinbox.setRange(desc.min_val, desc.max_val)
        self._spinbox.setSingleStep(desc.step)
        self._spinbox.setDecimals(desc.decimals)
        self._spinbox.setFixedWidth(80)

        self._set_value(desc.default)

        self._slider.valueChanged.connect(self._on_slider)
        self._spinbox.valueChanged.connect(self._on_spinbox)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)
        layout.addWidget(label,        0, 0)
        layout.addWidget(self._slider, 0, 1)
        layout.addWidget(self._spinbox, 0, 2)
        layout.setColumnStretch(1, 1)

    def _value_to_slider(self, value: float) -> int:
        d = self._desc
        steps = self._slider.maximum()
        ratio = (value - d.min_val) / (d.max_val - d.min_val) if d.max_val != d.min_val else 0
        return round(ratio * steps)

    def _slider_to_value(self, tick: int) -> float:
        d = self._desc
        steps = self._slider.maximum()
        return d.min_val + (tick / steps) * (d.max_val - d.min_val) if steps > 0 else d.min_val

    def _set_value(self, value: float) -> None:
        self._updating = True
        self._slider.setValue(self._value_to_slider(value))
        self._spinbox.setValue(value)
        self._updating = False

    def _on_slider(self, tick: int) -> None:
        if self._updating:
            return
        value = self._slider_to_value(tick)
        self._updating = True
        self._spinbox.setValue(value)
        self._updating = False
        self.value_changed.emit(self._desc.name, value)

    def _on_spinbox(self, value: float) -> None:
        if self._updating:
            return
        self._updating = True
        self._slider.setValue(self._value_to_slider(value))
        self._updating = False
        self.value_changed.emit(self._desc.name, value)

    def set_external_value(self, value: float) -> None:
        self._set_value(value)


class StageConfigWidget(QWidget):
    """
    Generic per-stage config panel.
    Auto-builds one ParamRow per parameter from the stage's get_params().
    """

    param_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._stage: PipelineStage | None = None
        self._rows: list[ParamRow] = []
        self._dynamic_widgets: list[QWidget] = []

        self._inner = QWidget()
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(4, 4, 4, 4)
        self._inner_layout.setSpacing(2)
        self._inner_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._inner)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._title = QLabel("No stage selected")
        self._title.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px;")

    def load_stage(self, stage: PipelineStage | None) -> None:
        self._stage = stage
        self._rebuild()

    def _rebuild(self) -> None:
        for w in self._dynamic_widgets:
            w.setParent(None)
        self._dynamic_widgets.clear()
        self._rows.clear()

        self._inner_layout.takeAt(self._inner_layout.count() - 1)

        if self._stage is None:
            self._inner_layout.addStretch(1)
            return

        self._title.setText(self._stage.name)

        # Text / string params: shown as label + QLineEdit
        for attr_name, label_text in self._stage.get_text_params():
            w = self._make_text_row(attr_name, label_text)
            self._inner_layout.addWidget(w)
            self._dynamic_widgets.append(w)

        # File-path params: shown as a Browse button + filename label
        for attr_name, label_text, file_filter in self._stage.get_path_params():
            w = self._make_path_row(attr_name, label_text, file_filter)
            self._inner_layout.addWidget(w)
            self._dynamic_widgets.append(w)

        # Slider params
        for desc in self._stage.get_params():
            row = ParamRow(desc)
            row.set_external_value(self._stage.get_param_value(desc.name))
            row.value_changed.connect(self._on_param_changed)
            self._inner_layout.addWidget(row)
            self._rows.append(row)
            self._dynamic_widgets.append(row)

        self._inner_layout.addStretch(1)

    def _make_text_row(self, attr_name: str, label_text: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(80)

        edit = QLineEdit(getattr(self._stage, attr_name, ""))
        edit.setPlaceholderText("(none)")

        def _on_edited(text: str) -> None:
            setattr(self._stage, attr_name, text)
            self.param_changed.emit()

        edit.textChanged.connect(_on_edited)
        layout.addWidget(lbl)
        layout.addWidget(edit, stretch=1)
        return container

    def _make_path_row(self, attr_name: str, label_text: str, file_filter: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(60)

        current_path = getattr(self._stage, attr_name, "")
        path_lbl = QLabel(Path(current_path).name if current_path else "—")
        path_lbl.setStyleSheet("color: #aaa; font-size: 11px;")

        btn = QPushButton("Browse…")
        btn.setFixedWidth(70)

        def _browse():
            path, _ = QFileDialog.getOpenFileName(self, f"Select {label_text}", current_path, file_filter)
            if path:
                setattr(self._stage, attr_name, path)
                # Invalidate any cache the stage may hold
                if hasattr(self._stage, "_cached_path"):
                    self._stage._cached_path = ""
                path_lbl.setText(Path(path).name)
                self.param_changed.emit()

        btn.clicked.connect(_browse)
        layout.addWidget(lbl)
        layout.addWidget(path_lbl, stretch=1)
        layout.addWidget(btn)
        return container

    def _on_param_changed(self, name: str, value: float) -> None:
        if self._stage is not None:
            self._stage.set_param_value(name, value)
            self.param_changed.emit()

    def refresh_values(self) -> None:
        if self._stage is None:
            return
        for row in self._rows:
            row.set_external_value(self._stage.get_param_value(row._desc.name))
