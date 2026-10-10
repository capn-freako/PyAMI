"""Tests for ``pyibisami.util.ami``: extracting adaptation curves from ``AMI_GetWave()`` output parameters."""

import logging

import numpy as np

from pyibisami.util.ami import get_cdr_adaptation, get_dfe_adaptation

OUT_PARAMS = [
    "(rx (cdr_ui 1.0e-10) (dfe_tap1 0.10) (dfe_tap2 0.02))",
    "(rx (cdr_ui 1.1e-10) (dfe_tap1 0.12) (dfe_tap2 0.03))",
]
# As returned by the bundled example Tx model's `AMI_GetWave()`: the root's closing ')' is missing.
UNPARSABLE = ["(example_tx (tx_tap_units 27) (taps[0] 0) (taps[1] 27) (tap_weights_[1] 1.0989)\n"]


def test_adaptation_extracted():
    np.testing.assert_allclose(get_cdr_adaptation(OUT_PARAMS), [1.0e-10, 1.1e-10])
    dfe = get_dfe_adaptation(OUT_PARAMS)
    assert sorted(dfe) == ["dfe_tap1", "dfe_tap2"]
    np.testing.assert_allclose(dfe["dfe_tap1"], [0.10, 0.12])


def test_unparsable_params_skip_with_warning(caplog):
    """Unparsable output parameters must not abort reporting; the adaptation plot is skipped, with a warning."""
    with caplog.at_level(logging.WARNING, logger="pyibisami.util.ami"):
        assert len(get_cdr_adaptation(UNPARSABLE)) == 0
        assert not get_dfe_adaptation(UNPARSABLE)
    assert [rec.getMessage().split(":")[0] for rec in caplog.records] == [
        "Skipping CDR adaptation", "Skipping DFE adaptation"]
    assert "(example_tx" in caplog.records[0].getMessage()
