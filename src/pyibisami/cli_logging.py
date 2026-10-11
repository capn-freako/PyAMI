"""
Console logging setup for the ``pyibisami`` command line tools.

The library itself never configures logging (it only installs a ``NullHandler``);
applications using it as a library decide where its messages go.
The command line tools, being applications, call ``setup_cli_logging()`` first.

Command results go to ``stdout`` (via ``click.echo()``);
progress and diagnostics go through logging, to ``stderr``.

Original Author: David Patterson

Original Date:   October 10, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

import logging
import sys

DEBUG_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
DEBUG_DATE_FORMAT = "%H:%M:%S"


class ConsoleFormatter(logging.Formatter):
    """User-facing format: bare ``INFO`` messages; ``LEVEL: message`` otherwise."""

    def __init__(self) -> None:
        super().__init__("%(levelname)s: %(message)s")
        self._info_formatter = logging.Formatter("%(message)s")

    def format(self, record: logging.LogRecord) -> str:
        if record.levelno == logging.INFO:
            return self._info_formatter.format(record)
        return super().format(record)


class _StderrHandler(logging.StreamHandler):
    """Writes to whatever ``sys.stderr`` is at emit time (as ``logging.lastResort`` does),
    so that redirection after setup (e.g. - by a test runner) is honored."""

    def __init__(self) -> None:
        logging.Handler.__init__(self)  # pylint: disable=non-parent-init-called

    @property  # type: ignore[override]
    def stream(self):
        return sys.stderr


def setup_cli_logging(debug: bool = False) -> None:
    """
    Send ``pyibisami`` log messages to the console (``stderr``).

    Only the ``pyibisami`` logger is configured, so ``debug`` doesn't
    also turn on the debugging output of third-party packages.

    Args:
        debug: Show ``DEBUG`` messages, too, in a detailed format
            (time, level & logger name), when ``True``;
            otherwise, show ``INFO`` and above, in a plain, user-facing format.
            Default: ``False``
    """
    pkg_logger = logging.getLogger("pyibisami")
    pkg_logger.setLevel(logging.DEBUG if debug else logging.INFO)
    handler = next((h for h in pkg_logger.handlers if isinstance(h, _StderrHandler)), None)
    if handler is None:  # Reuse ours on repeat calls; avoids duplicate output.
        handler = _StderrHandler()
        pkg_logger.addHandler(handler)
    handler.setFormatter(
        logging.Formatter(DEBUG_LOG_FORMAT, DEBUG_DATE_FORMAT) if debug else ConsoleFormatter())
