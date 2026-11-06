"""
Qt widgets for the IBIS model classes: ``IBISModel`` selection, ``Model`` information and plots.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   November 1, 2019

Copyright (c) 2019 by David Banas; All rights reserved World wide.
"""

from __future__ import annotations

import html
import weakref
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..events import InvalidValueError
from ..ibis.analog import Pin
from ..ibis.file import IBISModel
from ..ibis.model import Model
from .bridge import SignalBridge
from .plots import IVPlot, VTPlot

__all__ = ["IbisBrowser", "IbisSelector", "ModelInfo", "show_alerts"]


def _fmt(value: Any, unit: str = "") -> str:
    "A keyword value for display: numbers with ``:g``, typ/min/max lists joined, ``None`` as a dash."
    if value is None:
        return "—"
    if isinstance(value, (list, tuple)):
        return " / ".join(_fmt(v) for v in value) + (f" {unit}" if unit else "")
    if isinstance(value, float):
        return f"{value:g}" + (f" {unit}" if unit else "")
    return str(value)


class ModelInfo(QWidget):
    """The selected pin's ``[Pin]`` row (R/L/C blank: the ``[Package]`` default) and its ``Model``'s keyword values
    and derived characteristics (read-only)."""

    _PIN_ROWS: tuple[tuple[str, Callable[[Pin], Any], str], ...] = (
        ("Pin", lambda p: p.pin, ""),
        ("Signal", lambda p: p.signal, ""),
        ("R_pin", lambda p: p.r_pin, "Ω"),
        ("L_pin", lambda p: p.l_pin, "H"),
        ("C_pin", lambda p: p.c_pin, "F"),
    )
    _ROWS: tuple[tuple[str, Callable[[Model], Any], str], ...] = (
        ("Model", lambda m: m.name, ""),
        ("Model_type", lambda m: m.model_type, ""),
        ("C_comp (typ/min/max)", lambda m: m.c_comp, "F"),
        ("Voltage Range", lambda m: m.vrange, "V"),
        ("Temperature Range", lambda m: m.trange, "°C"),
        ("Vref", lambda m: m.vref, "V"),
        ("Vmeas", lambda m: m.vmeas, "V"),
        ("Rref", lambda m: m.rref, "Ω"),
        ("Cref", lambda m: m.cref, "F"),
        ("Zout", lambda m: m.zout, "Ω"),
        ("Slew rate", lambda m: m.slew, "V/ns"),
        ("Zin", lambda m: m.zin, "Ω"),
        ("V-T tables", lambda m: f"{len(m.rising)} rising, {len(m.falling)} falling", ""),
    )

    def __init__(self, model: Optional[Model] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        form = QFormLayout(self)
        self.values: dict[str, QLabel] = {}
        for name, _, _ in self._PIN_ROWS + self._ROWS:  # type: ignore[operator]
            label = QLabel()
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.values[name] = label
            form.addRow(name + ":", label)
        self.ami_status = QLabel()
        self.ami_status.setWordWrap(True)
        self.values["AMI"] = self.ami_status
        form.insertRow(len(self._PIN_ROWS) + 2, "AMI:", self.ami_status)  # After Model and Model_type.
        self.set_model(model)

    def set_model(self, model: Optional[Model], pin: Optional[Pin] = None, dll_path: Optional[Path] = None) -> None:
        """Show this model's values, and the pin's (``None``: clear).

        Keyword Args:
            dll_path: The model's executable for this platform, resolved (``IBISModel.dll_path``); when given, a
                missing file is flagged.
        """
        for name, get_pin, unit in self._PIN_ROWS:
            value = None if pin is None else get_pin(pin)
            self.values[name].setText("" if pin is None else ("" if value is None else _fmt(value, unit)))
        for name, get, unit in self._ROWS:
            self.values[name].setText("" if model is None else _fmt(get(model), unit))
        self._show_ami(model, dll_path)

    def _show_ami(self, model: Optional[Model], dll_path: Optional[Path]) -> None:
        "A check (or a cross) for an AMI executable for this platform; every ``Executable`` line in the tool tip."
        label = self.ami_status
        if model is None:
            label.setText("")
            label.setToolTip("")
            return
        if model.dll_file and (dll_path is None or dll_path.exists()):
            text = f'<span style="color:#2e9e44;">&#10003;</span> {html.escape(model.dll_file)}'
        elif model.dll_file:
            text = f'<span style="color:#d98c00;">&#9888;</span> {html.escape(model.dll_file)} (file not found)'
        elif model.is_ami:
            text = '<span style="color:#d64545;">&#10007;</span> no executable for this platform'
        else:
            text = "no [Algorithmic Model]"
        label.setText(text)
        lines = [f"{ex.direction or 'any'}: {ex.os} {ex.bits}-bit: {ex.dll}, {ex.ami}" for ex in model.ami_executables]
        label.setToolTip("\n".join(lines))


def _make_filterable(box: QComboBox) -> tuple[QCompleter, QLineEdit]:
    """Let the user type into ``box`` to filter its items (any part of the name, any case).

    Returns:
        Its completer and line edit.
    """
    line = QLineEdit()
    box.setEditable(True)
    box.setLineEdit(line)
    box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    completer = QCompleter(box.model(), box)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    box.setCompleter(completer)
    return completer, line


class IbisSelector(QWidget):
    """Select an ``IBISModel``'s component, pin and model.

    Each box offers its choices in a drop-down, and filters them as you type (any part of the name).
    ``selectionChanged`` is emitted (on the GUI thread) after any change of the selection, here or elsewhere.
    """

    selectionChanged = Signal()

    def __init__(self, ibis: IBISModel, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._ibis = ibis
        self.component_box = QComboBox()
        self.pin_box = QComboBox()
        self.model_box = QComboBox()
        for box, key in ((self.component_box, "component"), (self.pin_box, "pin"), (self.model_box, "model")):
            completer, line = _make_filterable(box)
            box.activated.connect(lambda ix, b=box, k=key: self._pick(k, b.itemText(ix)))
            completer.activated.connect(lambda text, k=key: self._pick(k, text))
            line.editingFinished.connect(lambda b=box, k=key: self._pick(k, b.currentText()))

        form = QFormLayout()
        form.addRow("Component:", self.component_box)
        form.addRow("Pin:", self.pin_box)
        form.addRow("Model:", self.model_box)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QLabel(f"<b>{ibis.file_name}</b> (IBIS {ibis.ibis_ver}, rev. {ibis.file_rev}, {ibis.date})")
        header.setWordWrap(True)
        layout.addWidget(header)
        layout.addLayout(form)

        self._bridge = SignalBridge(self, ibis.selection_changed)
        self._bridge.changed.connect(self.refresh)
        self.refresh()

    @property
    def ibis(self) -> IBISModel:
        "The model being selected from."
        return self._ibis

    def refresh(self) -> None:
        "Show the current selection and choices."
        ibis = self._ibis
        for box, choices, current in ((self.component_box, ibis.component_choices, ibis.component_name),
                                      (self.pin_box, ibis.pin_choices, ibis.pin_name),
                                      (self.model_box, ibis.model_choices, ibis.model_name)):
            box.blockSignals(True)
            if [box.itemText(i) for i in range(box.count())] != choices:
                box.clear()
                box.addItems(choices)
            box.setCurrentIndex(choices.index(current))
            box.blockSignals(False)
        self.selectionChanged.emit()

    def _pick(self, key: str, text: str) -> None:
        "Select a typed or picked name; text that isn't a choice (e.g. - a partial filter) just shows the selection."
        current = {"component": self._ibis.component_name, "pin": self._ibis.pin_name,
                   "model": self._ibis.model_name}[key]
        if text == current:
            return
        try:
            self._ibis.select(**{key: text})
        except InvalidValueError:
            pass  # Not one of the choices: put the box back.
        self.refresh()  # At once, too: the bridge's refresh comes a little later.


class IbisBrowser(QSplitter):
    """An ``IbisSelector`` with the selected pin's and model's information below it, beside a tab for each of the
    model's plots: Pulldown, Pullup (or the clamps, for a receiver), Rising and Falling. Tabs with nothing to show are
    hidden.

    Applications may add tabs to ``tabs`` (and hide them with ``show_tab()``).
    """

    def __init__(self, ibis: IBISModel, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.selector = IbisSelector(ibis)
        self.info = ModelInfo()
        info_area = QScrollArea()
        info_area.setWidget(self.info)
        info_area.setWidgetResizable(True)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self.selector)
        left_layout.addWidget(info_area, 1)
        self.pulldown_plot = IVPlot(side="down")
        self.pullup_plot = IVPlot(side="up")
        self.rising_plot = VTPlot(direction="rising")
        self.falling_plot = VTPlot(direction="falling")
        self.plots: list[IVPlot | VTPlot] = [self.pulldown_plot, self.pullup_plot, self.rising_plot, self.falling_plot]
        self.tabs = QTabWidget()
        for plot in self.plots:
            self.tabs.addTab(plot, plot.title)
        self.addWidget(left)
        self.addWidget(self.tabs)
        self.setStretchFactor(1, 1)
        self.setSizes([360, 1000])
        self._shown: Optional[tuple[Model, Pin]] = None
        self.selector.selectionChanged.connect(self._show_model)
        self._show_model()

    def show_tab(self, widget: QWidget, visible: bool) -> None:
        "Show or hide a tab; if the current one is hidden, the first one still shown becomes current."
        index = self.tabs.indexOf(widget)
        self.tabs.setTabVisible(index, visible)
        if not self.tabs.isTabVisible(self.tabs.currentIndex()):
            shown = [i for i in range(self.tabs.count()) if self.tabs.isTabVisible(i)]
            if shown:
                self.tabs.setCurrentIndex(shown[0])

    def visible_tabs(self) -> list[str]:
        "The titles of the tabs shown now."
        return [self.tabs.tabText(i) for i in range(self.tabs.count()) if self.tabs.isTabVisible(i)]

    def _show_model(self) -> None:
        ibis = self.selector.ibis
        model, pin = ibis.model, ibis.pin
        if self._shown is not None and self._shown[0] is model and self._shown[1] == pin:
            return
        new_model = self._shown is None or self._shown[0] is not model
        self._shown = (model, pin)
        self.info.set_model(model, pin, ibis.dll_path)
        if new_model:
            self.pulldown_plot.set_data(model.iv_data)
            self.pullup_plot.set_data(model.iv_data)
            self.rising_plot.set_waveforms(model.waveforms)
            self.falling_plot.set_waveforms(model.waveforms)
            for plot in self.plots:
                self.tabs.setTabText(self.tabs.indexOf(plot), plot.title)
                self.show_tab(plot, plot.has_data)


class _AlertRelay(QObject):
    "Re-emits an ``IBISModel``'s ``alert`` s as a Qt signal (delivered on the receiver's thread)."

    message = Signal(str)

    def __init__(self, parent: Optional[QObject], ibis: IBISModel) -> None:
        super().__init__(parent)
        emit = self.message.emit

        def relay(msg: str) -> None:
            try:
                emit(msg)
            except RuntimeError:  # The Qt object is already gone.
                pass

        disconnect = ibis.alert.connect(relay)
        self.destroyed.connect(lambda *_: disconnect())


_POPUPS: weakref.WeakKeyDictionary[IBISModel, _AlertRelay] = weakref.WeakKeyDictionary()


def show_alerts(ibis: IBISModel, parent: Optional[QWidget] = None) -> None:
    """Show each later ``alert`` of ``ibis`` in a message box. Calling it again for the same model does nothing.

    Needs a ``QApplication``.
    """
    if ibis in _POPUPS:
        return
    relay = _AlertRelay(None, ibis)  # Kept alive by ``_POPUPS``, as long as ``ibis`` is.
    relay.message.connect(lambda msg: QMessageBox.information(parent, "IBIS model", msg))
    _POPUPS[ibis] = relay
