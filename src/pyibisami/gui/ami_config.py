"""``AmiParamEditor``: a Qt widget for editing an ``AMIParamConfigurator``'s parameter values.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   December 17, 2016

Copyright (c) 2019 David Banas; all rights reserved World wide.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..ami.configurator import SIM_CORNERS, AMIParamConfigurator, ParamPath, display_name_part
from ..ami.parameter import AMIParameter
from ..events import InvalidValueError
from .bridge import SignalBridge

__all__ = ["AmiParamEditor", "load_preset", "save_preset"]

_COLUMNS = ("Parameter", "Value", "Format", "Description")
_EDITOR_MARGINS = (8, 2, 12, 2)  # Left, top, right, bottom (px) around each value editor, inside its cell.
_VALUE_COLUMN_MIN = 160  # px


def _padded(editor: QWidget) -> QWidget:
    "``editor`` in a container with margins, so it doesn't touch the cell's edges."
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(*_EDITOR_MARGINS)
    layout.addWidget(editor)
    return box


def save_preset(cfg: AMIParamConfigurator, file: str | Path) -> None:
    "Save ``cfg``'s current values as JSON, keyed by ``/``-joined ``.ami`` path."
    values = {"/".join(path): value for path, value in cfg.current_values().items()}
    Path(file).write_text(json.dumps({"root_name": cfg.root_name, "values": values}, indent=2), encoding="utf-8")


def load_preset(cfg: AMIParamConfigurator, file: str | Path) -> list[str]:
    """Apply values saved by ``save_preset()``.

    Returns:
        One message per entry that was skipped (unknown path, illegal value), plus one if the preset is for
        another model.
    """
    data = json.loads(Path(file).read_text(encoding="utf-8"))
    notes = []
    if data.get("root_name") != cfg.root_name:
        notes.append(f"Preset is for model {data.get('root_name')!r}, not {cfg.root_name!r}.")
    return notes + cfg.apply_values(data.get("values", {}))


class AmiParamEditor(QWidget):  # pylint: disable=too-many-instance-attributes
    """Edit an ``AMIParamConfigurator``'s settable parameters, live.

    Each edit calls ``set_param_val()`` at once; an illegal value is reported below the tree and the editor shows
    the current value again. Changes made elsewhere (e.g. - by an optimizer thread) are shown as they happen.
    Parameters that aren't settable (Out/Info, Corner, Table, ...) are listed read-only with the value sent.
    """

    def __init__(self, cfg: AMIParamConfigurator, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._cfg = cfg
        self._editors: dict[ParamPath, QWidget] = {}
        self._fixed_items: list[tuple[ParamPath, QTreeWidgetItem]] = []

        self._corner = QComboBox()
        self._corner.addItems(list(SIM_CORNERS))
        self._corner.setToolTip("Simulation corner: picks each Corner parameter's value.")
        self._corner.currentTextChanged.connect(self._set_corner)
        reset = QPushButton("Reset to defaults")
        reset.clicked.connect(self._reset)
        save = QPushButton("Save preset...")
        save.clicked.connect(self._save)
        load = QPushButton("Load preset...")
        load.clicked.connect(self._load)
        bar = QHBoxLayout()
        bar.addWidget(QLabel(f"Model: <b>{cfg.root_name}</b>"))
        bar.addStretch()
        bar.addWidget(QLabel("Corner:"))
        bar.addWidget(self._corner)
        for button in (reset, save, load):
            bar.addWidget(button)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(_COLUMNS))
        self.tree.setHeaderLabels(list(_COLUMNS))
        self.tree.setAlternatingRowColors(True)
        self.status = QLabel()
        self.status.setWordWrap(True)

        layout = QVBoxLayout(self)
        if cfg.description:
            desc = QLabel(cfg.description)
            desc.setWordWrap(True)
            layout.addWidget(desc)
        layout.addLayout(bar)
        layout.addWidget(self.tree)
        layout.addWidget(self.status)

        self._build_tree()
        self.tree.expandAll()
        for col in range(len(_COLUMNS) - 1):
            self.tree.resizeColumnToContents(col)
        self.tree.setColumnWidth(1, max(self.tree.columnWidth(1), _VALUE_COLUMN_MIN))
        self._bridge = SignalBridge(self, cfg.values_changed, cfg.sim_corner_changed)
        self._bridge.changed.connect(self.refresh)
        self.refresh()

    @property
    def configurator(self) -> AMIParamConfigurator:
        "The configurator being edited."
        return self._cfg

    def editor(self, path: ParamPath) -> QWidget:
        "The editor widget for a settable parameter."
        return self._editors[tuple(path)]

    # Building.

    def _build_tree(self) -> None:
        settable = dict(self._cfg.iter_settable())
        for root in ("Model_Specific", "Reserved_Parameters"):
            params = self._cfg.ami_param_defs[root]
            top = QTreeWidgetItem(self.tree, [root])
            self._add_branch(top, params, (root,), settable)  # type: ignore[arg-type]
            if root == "Reserved_Parameters":
                top.setExpanded(False)

    def _add_branch(
        self, parent: QTreeWidgetItem, params: dict[str, Any], prefix: ParamPath,
        settable: dict[ParamPath, AMIParameter],
    ) -> None:
        for name, param in params.items():
            if name == "description":
                parent.setText(3, str(param))
                continue
            path = (*prefix, name)
            label = display_name_part(name)
            item = QTreeWidgetItem(parent, [label if label == name else f"{label} ({name})"])
            if isinstance(param, AMIParameter):
                item.setText(2, f"{param.pformat} {param.ptype} ({param.pusage})")
                item.setText(3, param.pdescription)
                item.setToolTip(0, param.pdescription)
                if path in settable:
                    editor = self._make_editor(path, param)
                    editor.setToolTip(param.pdescription)
                    self._editors[path] = editor
                    self.tree.setItemWidget(item, 1, _padded(editor))
                else:
                    self._fixed_items.append((path, item))
            else:
                self._add_branch(item, param, path, settable)

    def _make_editor(self, path: ParamPath, param: AMIParameter) -> QWidget:
        editor: QWidget
        if param.ptype == "Boolean":
            editor = QCheckBox()
            editor.toggled.connect(lambda value, p=path: self._set(p, value))
        elif param.choices is not None:
            editor = QComboBox()
            tips = param.plist_tip if param.pformat == "List" and param.plist_tip else None
            for ix, value in enumerate(param.choices):
                text = tips[ix] if tips and ix < len(tips) else str(value)
                editor.addItem(text if text == str(value) else f"{text} ({value})", value)
            editor.activated.connect(lambda ix, p=path, box=editor: self._set(p, box.itemData(ix)))
        elif param.pformat == "Range" and param.ptype == "Integer":
            editor = QSpinBox()
            editor.setRange(int(param.pmin), int(param.pmax))
            editor.editingFinished.connect(lambda p=path, box=editor: self._set(p, box.value()))
        elif param.pformat == "Range":
            editor = QDoubleSpinBox()
            editor.setDecimals(6)
            editor.setRange(float(param.pmin), float(param.pmax))
            editor.setSingleStep((float(param.pmax) - float(param.pmin)) / 100 or 0.1)
            editor.editingFinished.connect(lambda p=path, box=editor: self._set(p, box.value()))
        else:  # Value
            editor = QLineEdit()
            editor.editingFinished.connect(lambda p=path, box=editor: self._set(p, box.text()))
        return editor

    # Core -> widgets.

    def refresh(self) -> None:
        "Show the configurator's current values."
        values = self._cfg.current_values()
        for path, editor in self._editors.items():
            value = values[path]
            editor.blockSignals(True)
            try:
                if isinstance(editor, QCheckBox):
                    editor.setChecked(bool(value))
                elif isinstance(editor, QComboBox):
                    editor.setCurrentIndex(max(editor.findData(value), 0))
                elif isinstance(editor, (QSpinBox, QDoubleSpinBox)):
                    editor.setValue(value)
                elif isinstance(editor, QLineEdit):
                    editor.setText(str(value))
            finally:
                editor.blockSignals(False)
        for path, item in self._fixed_items:
            item.setText(1, str(self._cfg.fetch_param_val(list(path))))
        self._corner.blockSignals(True)
        self._corner.setCurrentText(self._cfg.sim_corner)
        self._corner.blockSignals(False)

    # Widgets -> core.

    def _set(self, path: ParamPath, value: Any) -> None:
        try:
            self._cfg.set_param_val(path, value)
        except InvalidValueError as err:
            self._report(str(err), error=True)
            self.refresh()
        else:
            self._report("")

    def _set_corner(self, corner: str) -> None:
        self._cfg.sim_corner = corner

    def _reset(self) -> None:
        self._cfg.reset_to_defaults()
        self._report("Reset to defaults.")

    def _save(self) -> None:
        file, _ = QFileDialog.getSaveFileName(self, "Save AMI preset", f"{self._cfg.root_name}.json", "JSON (*.json)")
        if file:
            save_preset(self._cfg, file)
            self._report(f"Saved {file}.")

    def _load(self) -> None:
        file, _ = QFileDialog.getOpenFileName(self, "Load AMI preset", "", "JSON (*.json)")
        if file:
            try:
                notes = load_preset(self._cfg, file)
            except (OSError, ValueError) as err:
                self._report(f"Couldn't load {file}: {err}", error=True)
                return
            self._report("\n".join(notes) or f"Loaded {file}.", error=bool(notes))

    def _report(self, msg: str, error: bool = False) -> None:
        self.status.setText(msg)
        self.status.setStyleSheet("color: red;" if error else "")
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
