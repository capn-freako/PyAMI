"""
Console logging setup for the ``pyibisami`` command line tools.

The library itself never configures logging (it only installs a ``NullHandler``);
applications using it as a library decide where its messages go.
The command line tools, being applications, call ``setup_cli_logging()`` first.

Original Author: David Patterson

Original Date:   October 10, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

import logging

CLI_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
CLI_DATE_FORMAT = "%H:%M:%S"


def setup_cli_logging(debug: bool = False) -> None:
    """
    Send ``pyibisami`` log messages to the console (``stderr``).

    Only the ``pyibisami`` logger is configured, so ``debug`` doesn't
    also turn on the debugging output of third-party packages.

    Args:
        debug: Show ``DEBUG`` messages, too, when ``True``; otherwise, ``INFO`` and above.
            Default: ``False``
    """
    pkg_logger = logging.getLogger("pyibisami")
    pkg_logger.setLevel(logging.DEBUG if debug else logging.INFO)
    if not any(getattr(handler, "_pyibisami_cli", False) for handler in pkg_logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(CLI_LOG_FORMAT, CLI_DATE_FORMAT))
        handler._pyibisami_cli = True  # type: ignore[attr-defined]  # Marks ours; avoids duplicates on repeat calls.
        pkg_logger.addHandler(handler)
