"""Modal dialogs behind ``AMIParamConfigurator.open_gui()`` and ``IBISModel.open_gui()``.

Original Author: David Patterson

Original Date:   November 5, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

from __future__ import annotations

from collections.abc import Callable
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


def _run(title: str, content: QWidget, parent: Optional[QWidget], undo: Callable[[], None]) -> bool:
    """Show ``content`` in a modal OK/Cancel dialog. Edits apply as they're made; Cancel (or Esc) calls ``undo``.

    Returns:
        ``True`` if closed with OK.
    """
    ensure_app()
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout = QVBoxLayout(dialog)
    layout.addWidget(content)
    layout.addWidget(buttons)
    dialog.resize(900, 600)
    try:
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if not accepted:
            undo()
        return accepted
    finally:
        # A parent would otherwise keep the dialog (and its widgets, still listening to the core object) for good.
        dialog.deleteLater()


def edit_ami_params(cfg: AMIParamConfigurator, parent: Optional[QWidget] = None) -> bool:
    """Edit ``cfg``'s values in a modal dialog; they apply as they're made, and Cancel puts back the values (and
    ``sim_corner``) it opened with. ``True`` if closed with OK."""
    ensure_app()
    values, corner = cfg.current_values(), cfg.sim_corner

    def undo() -> None:
        cfg.apply_values(values, strict=True)
        cfg.sim_corner = corner

    return _run(f"AMI parameters: {cfg.root_name}", AmiParamEditor(cfg), parent, undo)


def select_ibis_model(ibis: IBISModel, parent: Optional[QWidget] = None) -> bool:
    """Select ``ibis``'s component/pin/model in a modal dialog; later ``alert`` s pop up. The selection follows the
    dialog, and Cancel puts back the one it opened with. ``True`` if closed with OK."""
    ensure_app()
    show_alerts(ibis, parent)
    selection = (ibis.component_name, ibis.pin_name, ibis.model_name)
    return _run(f"IBIS model: {ibis.file_name}", IbisBrowser(ibis), parent, lambda: ibis.select(*selection))
