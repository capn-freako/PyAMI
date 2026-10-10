"""
Traits/UI views for the ``pyibisami`` model classes.

Requires the ``gui`` extra (``pip install 'pyibis-ami[gui]'``), plus a Qt binding.
When no binding is chosen by the caller (via ``QT_API``), ``pyface`` picks
the first one installed, preferring PySide6.

Original Author: David Patterson

Original Date:   October 10, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

try:
    import traitsui  # noqa: F401  # pylint: disable=unused-import
except ImportError as err:
    raise ImportError(
        "The pyibisami GUI requires the `gui` extra: pip install 'pyibis-ami[gui]'"
    ) from err
