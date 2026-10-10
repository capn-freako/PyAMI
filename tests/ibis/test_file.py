import logging

import pytest

from pyibisami.ibis.file import IBISModel


def test_ibis_model_construction(ibis_test_file):
    """IBISModel should construct without error from a valid IBIS file.

    Regression test: construction previously crashed with an `AttributeError`
    (`datetime.timezone` doesn't exist on the `datetime.datetime` class)
    while time-stamping its own log messages.
    """
    model = IBISModel(ibis_test_file, debug=False)
    assert model.file_name == "example_tx.ibs"


def test_alerts_are_logged_and_fired(ibis_test_file, caplog):
    """User-facing notices go to the logger and the ``alert`` event; no GUI involved."""
    with caplog.at_level(logging.INFO, logger="pyibisami.ibis.file"):
        model = IBISModel(ibis_test_file)
    assert [rec.levelno for rec in caplog.records if "Model `example_tx`" in rec.getMessage()] == [logging.INFO]

    fired = []
    model.observe(lambda event: fired.append(event.new), "alert")
    model._mod_changed(model.mod)  # pylint: disable=protected-access
    assert len(fired) == 1 and "Model `example_tx`" in fired[0]


def test_show_alerts_pops_up_once(ibis_test_file, monkeypatch):
    pytest.importorskip("traitsui")
    from pyibisami.gui import ibis as gui_ibis

    shown = []
    monkeypatch.setattr(gui_ibis, "message", lambda msg, title: shown.append(msg))
    model = IBISModel(ibis_test_file)
    gui_ibis.show_alerts(model)
    gui_ibis.show_alerts(model)
    model._mod_changed(model.mod)  # pylint: disable=protected-access
    assert len(shown) == 1
