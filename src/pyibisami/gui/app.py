"""``pyibisami-gui``: a standalone viewer for IBIS (``.ibs``) and AMI parameter (``.ami``) files.

Original Author: David Patterson

Original Date:   November 5, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QTabWidget, QWidget

from ..ami.configurator import AMIParamConfigurator
from ..cli_logging import setup_cli_logging
from ..ibis.file import IBISModel
from .ami_config import AmiParamEditor
from .dialogs import ensure_app
from .ibis import IbisBrowser

__all__ = ["MainWindow", "main", "open_in_text_editor"]

logger = logging.getLogger(__name__)

_FILTERS = "IBIS or AMI files (*.ibs *.ami);;IBIS files (*.ibs);;AMI files (*.ami);;All files (*)"


def open_in_text_editor(path: str | Path) -> None:
    """Open a file in the operating system's text editor (we don't manage editing, or reload).

    Windows: the editor registered for the file type's "edit" verb, else Notepad. macOS: the default text editor
    (``open -t``). Others: ``xdg-open``.

    Raises:
        OSError: No editor could be started.
    """
    path = str(path)
    if sys.platform == "win32":
        try:
            os.startfile(path, "edit")  # type: ignore[attr-defined]  # pylint: disable=no-member
        except OSError:  # No "edit" verb registered for ``.ibs``/``.ami`` (the usual case).
            subprocess.Popen(["notepad.exe", path])  # pylint: disable=consider-using-with
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-t", path])  # pylint: disable=consider-using-with
    else:
        subprocess.Popen(["xdg-open", path])  # pylint: disable=consider-using-with


class MainWindow(QMainWindow):
    """Open an ``.ibs`` file to browse its components, pins and models (information, I-V curves, V-T waveforms,
    the selected model's AMI parameters, and parsing warnings); or an ``.ami`` file to edit its parameters."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PyIBIS-AMI")
        self.resize(1200, 750)
        self.ibis: Optional[IBISModel] = None
        self.browser: Optional[IbisBrowser] = None
        self.warnings = QPlainTextEdit()
        self.warnings.setReadOnly(True)
        self._ami_tab_index = -1
        self._ami_shown: Optional[Path] = None  # The .ami the AMI tab shows (rebuilt only when it changes).
        self._configurators: dict[Path, AMIParamConfigurator] = {}  # Kept, so values survive model changes.
        self.ibis_path: Optional[Path] = None  # The open .ibs file.
        self.ami_path: Optional[Path] = None  # The open .ami file, or the selected model's.

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._choose_file)
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        self.open_ibis_action = QAction("Open &IBIS file", self)
        self.open_ibis_action.setShortcut("Ctrl+E")
        self.open_ibis_action.triggered.connect(lambda: self._open(self.ibis_path))
        self.open_ami_action = QAction("Open &AMI file", self)
        self.open_ami_action.setShortcut("Ctrl+Shift+E")
        self.open_ami_action.triggered.connect(lambda: self._open(self.ami_path))
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)
        tools_menu = self.menuBar().addMenu("&Tools")
        tools_menu.setToolTipsVisible(True)
        tools_menu.addAction(self.open_ibis_action)
        tools_menu.addAction(self.open_ami_action)
        self._update_actions()
        self.setCentralWidget(QLabel("Open an IBIS (.ibs) or AMI (.ami) file (File > Open)."))

    def open_file(self, file: str | Path) -> bool:
        "Show a ``.ibs`` or ``.ami`` file; on failure, say why (and keep showing the previous one)."
        path = Path(file)
        try:
            if path.suffix.lower() == ".ami":
                self._show_ami(path)
            else:
                self._show_ibis(path)
        except Exception as err:  # pylint: disable=broad-exception-caught  # Any failure: say why, keep the old file.
            logger.error("Couldn't open %s: %s", path, err, exc_info=not isinstance(err, (OSError, ValueError)))
            QMessageBox.critical(self, "Couldn't open file", f"{path}:\n\n{err}")
            return False
        self.setWindowTitle(f"PyIBIS-AMI: {path.name}")
        return True

    def _update_actions(self) -> None:
        self.open_ibis_action.setEnabled(self.ibis_path is not None)
        self.open_ami_action.setEnabled(self.ami_path is not None and self.ami_path.exists())
        for action, path in ((self.open_ibis_action, self.ibis_path), (self.open_ami_action, self.ami_path)):
            action.setToolTip(f"Open {path} in your text editor" if path else "No file")

    def _open(self, path: Optional[Path]) -> None:
        if path is None:
            return
        try:
            open_in_text_editor(path)
        except OSError as err:
            QMessageBox.warning(self, "Couldn't start a text editor", f"{path}:\n\n{err}")

    def _choose_file(self) -> None:
        file, _ = QFileDialog.getOpenFileName(self, "Open IBIS or AMI file", "", _FILTERS)
        if file:
            self.open_file(file)

    def _show_ami(self, path: Path) -> None:
        cfg = AMIParamConfigurator(path.read_text(encoding="utf-8"))
        tabs = QTabWidget()
        tabs.addTab(AmiParamEditor(cfg), "AMI parameters")
        warnings = QPlainTextEdit("\n".join(cfg.ami_parsing_errors) or "No warnings.")
        warnings.setReadOnly(True)
        tabs.addTab(warnings, "Warnings")
        self.ibis, self.browser = None, None
        self.ibis_path, self.ami_path = None, path
        self.setCentralWidget(tabs)
        self._update_actions()

    def _show_ibis(self, path: Path) -> None:
        ibis = IBISModel(path)
        browser = IbisBrowser(ibis)
        self.warnings = QPlainTextEdit()
        self.warnings.setReadOnly(True)
        self._ami_tab_index = browser.tabs.addTab(QLabel(), "AMI parameters")
        browser.tabs.addTab(self.warnings, "Warnings")
        browser.selector.selectionChanged.connect(self._model_changed)
        self.ibis, self.browser = ibis, browser
        self.ibis_path = path
        self._ami_shown = None
        self._configurators.clear()
        self.setCentralWidget(browser)
        self._model_changed()

    def _model_changed(self) -> None:
        "Show the selected model's AMI parameters and the warnings."
        if self.ibis is None or self.browser is None:
            return
        ami_path = self.ibis.ami_path
        self.ami_path = ami_path
        self._update_actions()
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
        if ami_path is None or ami_path != self._ami_shown:  # Keep the editor (and its scroll) if it's the same file.
            widget: QWidget
            if cfg is not None:
                widget = AmiParamEditor(cfg)
            elif ami_path is not None:
                widget = QLabel(f"Couldn't load {ami_path}:\n{ami_errors[0]}")
            else:
                widget = QLabel()
            tabs = self.browser.tabs
            current = tabs.currentIndex()
            old = tabs.widget(self._ami_tab_index)
            tabs.removeTab(self._ami_tab_index)
            tabs.insertTab(self._ami_tab_index, widget, "AMI parameters")
            if old is not None:
                old.deleteLater()
            tabs.setCurrentIndex(current)
            self._ami_shown = ami_path
            self.browser.show_tab(widget, ami_path is not None)
        model = self.ibis.model
        text = [f"IBIS: {self.ibis.ibis_parsing_errors}"]
        if model.spec_warnings:
            text += ["", f"[Model] {model.name}:"] + [f"- {w}" for w in model.spec_warnings]
        if ami_errors:
            text += ["", f"AMI ({ami_path}):"] + [f"- {e}" for e in ami_errors]
        self.warnings.setPlainText("\n".join(text))
        self.statusBar().showMessage(f"{self.ibis.component_name} / {self.ibis.pin_name} / {model.name}")


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("file", required=False, type=click.Path(exists=True, dir_okay=False))
@click.option("-d", "--debug", is_flag=True, help="Log debugging details.")
def main(file: Optional[str], debug: bool) -> None:
    "Browse an IBIS (.ibs) file, or edit an AMI parameter (.ami) file."
    setup_cli_logging(debug)
    app = ensure_app()
    window = MainWindow()
    window.show()
    if file:
        window.open_file(file)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
