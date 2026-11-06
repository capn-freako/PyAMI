"""Modal dialogs behind ``AMIParamConfigurator.open_gui()`` and ``IBISModel.open_gui()``.

Original Author: David Patterson

Original Date:   November 5, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QVBoxLayout, QWidget

from ..ami.configurator import AMIParamConfigurator
from ..ibis.file import IBISModel
from .ami_config import AmiParamEditor
from .ibis import IbisBrowser, show_alerts

__all__ = ["edit_ami_params", "ensure_app", "select_ibis_model"]


def ensure_app() -> QApplication:
    "The running ``QApplication``, created if there's none."
    app = QApplication.instance()
    return app if isinstance(app, QApplication) else QApplication([])


def _run(title: str, content: QWidget, parent: Optional[QWidget]) -> bool:
    ensure_app()
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
    buttons.accepted.connect(dialog.accept)
    layout = QVBoxLayout(dialog)
    layout.addWidget(content)
    layout.addWidget(buttons)
    dialog.resize(900, 600)
    return dialog.exec() == QDialog.DialogCode.Accepted


def edit_ami_params(cfg: AMIParamConfigurator, parent: Optional[QWidget] = None) -> bool:
    "Edit ``cfg``'s values in a modal dialog (changes apply as they're made). ``True`` if closed with OK."
    ensure_app()
    return _run(f"AMI parameters: {cfg.root_name}", AmiParamEditor(cfg), parent)


def select_ibis_model(ibis: IBISModel, parent: Optional[QWidget] = None) -> bool:
    """Select ``ibis``'s component/pin/model in a modal dialog; later ``alert`` s pop up.
    ``True`` if closed with OK."""
    ensure_app()
    show_alerts(ibis, parent)
    return _run(f"IBIS model: {ibis.file_name}", IbisBrowser(ibis), parent)
