"""``IbisAmiBrowser``: an ``IbisBrowser`` with the selected model's AMI parameters and the parsing warnings.

Original Author: David Patterson

Original Date:   November 6, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QWidget

from ..ami.configurator import AMIParamConfigurator
from ..ibis.file import IBISModel
from .ami_config import AmiParamEditor
from .ibis import IbisBrowser

__all__ = ["IbisAmiBrowser"]


class IbisAmiBrowser(IbisBrowser):
    """An ``IbisBrowser`` with two more tabs: the selected model's AMI parameters (an ``AmiParamEditor``) and the
    IBIS/AMI parsing warnings. An embeddable widget (e.g. - for PyBERT); ``pyibisami-gui`` shows one per ``.ibs`` file.

    Each ``.ami`` file's ``AMIParamConfigurator`` is kept for as long as this widget, so its values survive model
    changes. ``configurator`` is the selected model's: ``None`` if the model has no executable for this platform, or
    its ``.ami`` file won't load. ``amiChanged`` is emitted (on the GUI thread) when ``configurator`` changes.

    Edits apply as they're made; there's no Cancel (wrap it in a dialog that restores ``current_values()`` for one).
    """

    amiChanged = Signal()

    def __init__(self, ibis: IBISModel, parent: Optional[QWidget] = None) -> None:
        super().__init__(ibis, parent)
        self.warnings = QPlainTextEdit()
        self.warnings.setReadOnly(True)
        self._ami_tab: QWidget = QLabel()
        self.tabs.addTab(self._ami_tab, "AMI parameters")
        self.tabs.addTab(self.warnings, "Warnings")
        self._configurators: dict[Path, AMIParamConfigurator] = {}
        self._configurator: Optional[AMIParamConfigurator] = None
        self._ami_shown: Optional[Path] = None  # The .ami the AMI tab shows (rebuilt only when it changes).
        self.selector.selectionChanged.connect(self._model_changed)
        self._model_changed()

    @property
    def configurator(self) -> Optional[AMIParamConfigurator]:
        "The selected model's AMI parameter values; ``None`` if it has none for this platform, or they won't load."
        return self._configurator

    @property
    def ami_path(self) -> Optional[Path]:
        "The selected model's ``.ami`` file for this platform (``IBISModel.ami_path``); ``None`` if none."
        return self.selector.ibis.ami_path

    def _model_changed(self) -> None:
        "Show the selected model's AMI parameters and the warnings."
        ibis = self.selector.ibis
        ami_path = self.ami_path
        cfg: Optional[AMIParamConfigurator] = None
        ami_errors: list[str] = []
        if ami_path is not None:
            try:
                if ami_path not in self._configurators:
                    self._configurators[ami_path] = AMIParamConfigurator(ami_path.read_text(encoding="utf-8"))
                cfg = self._configurators[ami_path]
                ami_errors = cfg.ami_parsing_errors
            except (OSError, ValueError, RuntimeError) as err:
                ami_errors = [str(err)]
        if ami_path is None or ami_path != self._ami_shown:  # Keep the editor (and its scroll) for the same file.
            self._show_ami_tab(cfg, ami_path, ami_errors)
        if cfg is not self._configurator:
            self._configurator = cfg
            self.amiChanged.emit()
        model = ibis.model
        text = [f"IBIS: {ibis.ibis_parsing_errors}"]
        if model.spec_warnings:
            text += ["", f"[Model] {model.name}:"] + [f"- {w}" for w in model.spec_warnings]
        if ami_errors:
            text += ["", f"AMI ({ami_path}):"] + [f"- {e}" for e in ami_errors]
        self.warnings.setPlainText("\n".join(text))

    def _show_ami_tab(self, cfg: Optional[AMIParamConfigurator], ami_path: Optional[Path], errors: list[str]) -> None:
        "Put the AMI tab's new contents in place (hidden when the model has no ``.ami`` for this platform)."
        widget: QWidget
        if cfg is not None:
            widget = AmiParamEditor(cfg)
        elif ami_path is not None:
            widget = QLabel(f"Couldn't load {ami_path}:\n{errors[0]}")
        else:
            widget = QLabel()
        tabs = self.tabs
        current, index = tabs.currentIndex(), tabs.indexOf(self._ami_tab)
        tabs.removeTab(index)
        tabs.insertTab(index, widget, "AMI parameters")
        self._ami_tab.deleteLater()
        self._ami_tab = widget
        tabs.setCurrentIndex(current)
        self._ami_shown = ami_path
        self.show_tab(widget, ami_path is not None)
