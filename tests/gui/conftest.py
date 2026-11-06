"""The GUI tests need the ``gui`` extra and pytest-qt; they run headless."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "QtAgg")

pytest.importorskip("PySide6")
pytest.importorskip("matplotlib")
pytest.importorskip("pytestqt")
