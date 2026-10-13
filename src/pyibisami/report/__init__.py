"""
IBIS-AMI model test reporting: PDF reports (*ReportLab*) and plots (*Matplotlib*).

Requires the ``report`` extra (Matplotlib, ReportLab, SciPy): ``pip install 'pyibis-ami[report]'``.
The test definitions themselves (``pyibisami.testing``) don't.

Original Author: David Patterson

Original Date:   October 10, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

try:
    import matplotlib  # noqa: F401  # pylint: disable=unused-import
    import reportlab  # noqa: F401  # pylint: disable=unused-import
    import scipy  # noqa: F401  # pylint: disable=unused-import
except ImportError as err:
    raise ImportError(
        "pyibisami test reporting requires the `report` extra: pip install 'pyibis-ami[report]'"
    ) from err
