"""
Qt (PySide6) widgets and dialogs for the ``pyibisami`` model classes.

Requires the ``gui`` extra: ``pip install 'pyibis-ami[gui]'``.

The widgets are plain ``QWidget`` s, so applications (e.g. - PyBERT) can embed them:

- ``AmiParamEditor``: edit an ``AMIParamConfigurator``'s parameter values.
- ``IbisSelector``: select an ``IBISModel``'s component, pin and model; ``IbisBrowser`` adds model tabs.
- ``ModelInfo``: a ``Model``'s keyword values.
- ``IVPlot``, ``VTPlot``: a ``Model``'s I-V curves and V-T waveforms.

``show_alerts(ibis)`` pops up an ``IBISModel``'s ``alert`` s; ``pyibisami-gui`` is a standalone viewer.

Original Author: David Patterson

Original Date:   November 5, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

try:
    import matplotlib  # noqa: F401  # pylint: disable=unused-import
    import PySide6  # noqa: F401  # pylint: disable=unused-import
except ImportError as err:
    raise ImportError(
        "The pyibisami GUI requires the `gui` extra: pip install 'pyibis-ami[gui]'"
    ) from err

from .ami_config import AmiParamEditor
from .ibis import IbisBrowser, IbisSelector, ModelInfo, show_alerts
from .plots import IVPlot, VTPlot

__all__ = ["AmiParamEditor", "IVPlot", "IbisBrowser", "IbisSelector", "ModelInfo", "VTPlot", "show_alerts"]
