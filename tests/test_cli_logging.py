"""Tests for the command line tools' console logging setup."""

import logging

import pytest

from pyibisami.cli_logging import setup_cli_logging


@pytest.fixture
def pkg_logger():
    """The ``pyibisami`` logger, restored after the test."""
    logger = logging.getLogger("pyibisami")
    handlers, level = list(logger.handlers), logger.level
    yield logger
    logger.handlers[:] = handlers
    logger.setLevel(level)


def test_setup_is_idempotent_and_scoped(pkg_logger, capsys):
    setup_cli_logging()
    setup_cli_logging(debug=True)
    assert sum(getattr(h, "_pyibisami_cli", False) for h in pkg_logger.handlers) == 1  # No duplicate output.
    assert pkg_logger.level == logging.DEBUG
    assert logging.getLogger().level == logging.WARNING  # Root (third-party) untouched.

    logging.getLogger("pyibisami.ami.config").info("Building 'x' from 'y'...")
    err = capsys.readouterr().err
    assert "INFO" in err and "pyibisami.ami.config: Building 'x' from 'y'..." in err
