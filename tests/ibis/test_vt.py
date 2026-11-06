"""V-T waveform tables (``[Rising Waveform]``/``[Falling Waveform]``; IBIS 8.0 Section 6.1, p.107-108)."""

import math

import numpy as np
import pytest

from pyibisami.ibis.file import IBISModel
from pyibisami.ibis.iv import IVCurve
from pyibisami.ibis.vt import Fixture, VTWaveform

WAVEFORMS = """
[Rising Waveform]
R_fixture = 50
V_fixture = 0.0
| Time            V(typ)              V(min)              V(max)
   0.0000s       25.2100mV           NA                  43.5700mV
   0.2000ns       0.7799V            NA                   1.3400V
  10.0000ns       1.7780V            NA                   1.9670V
[Composite Current]
| Time       I(typ)   I(min)  I(max)
0         4.243E-05 NA  NA
4.00E-11  4.244E-05 NA  NA
[Rising Waveform]
R_fixture = 50
V_fixture = 1.8
V_fixture_min = 1.62
V_fixture_max = 1.98
C_fixture = 5p
   0.0     0.9     0.8     1.0
   1n      1.8     1.62    1.98
[Falling Waveform]
R_fixture = 50
V_fixture = 1.8
   0.0     1.8     1.62    1.98
   1n      0.9     0.8     1.0
[Falling Waveform]
V_fixture = 0.0
   0.0     0.9     NA      NA
   1n      0.0     NA      NA
"""


@pytest.fixture
def wave_model(ibis_test_file):
    text = ibis_test_file.read_text(encoding="utf-8").replace("[END]", WAVEFORMS + "\n[END]")
    return IBISModel.from_text(text).model


def test_waveforms_parsed_in_file_order(wave_model):
    """Every table is kept (several per direction), and [Composite Current] after one doesn't break it."""
    assert [w.direction for w in wave_model.waveforms] == ["rising", "rising", "falling"]
    assert len(wave_model.rising) == 2 and len(wave_model.falling) == 1
    first = wave_model.rising[0]
    np.testing.assert_allclose(first.t, [0.0, 0.2e-9, 10e-9])
    np.testing.assert_allclose(first.v_typ, [25.21e-3, 0.7799, 1.778])
    assert first.na_min.all() and not first.na_max.any()
    assert first.label == "Rising, 50 Ohm to 0 V"


def test_table_without_r_fixture_is_skipped_with_a_warning(wave_model):
    """R_fixture and V_fixture are required (p.108)."""
    assert any("R_fixture" in w and "Falling Waveform" in w for w in wave_model.spec_warnings)


def test_fixture_voltage_per_corner(wave_model):
    second = wave_model.rising[1]
    assert second.fixture == Fixture(50.0, 1.8, 1.62, 1.98, c_fixture=5e-12)
    assert [second.at(c)[2] for c in ("typ", "min", "max")] == pytest.approx([1.8, 1.62, 1.98])
    assert wave_model.rising[0].at("max")[2] == 0.0  # No V_fixture_max: V_fixture.


def test_na_corner_left_out_of_series(wave_model):
    first = wave_model.rising[0]
    assert [s.corner for s in first.series()] == ["typ", "max"]
    t, v, _ = first.at("min")
    assert len(t) == len(v) == 0
    assert all(not math.isnan(x) for s in first.series() for x in s.v)


@pytest.mark.parametrize("rows, match", [
    ([(0.0, 1.0, None, None)], "at least two rows"),
    ([(1.0, 1.0, None, None), (0.5, 1.0, None, None)], "times must increase"),
])
def test_bad_tables_rejected(rows, match):
    with pytest.raises(ValueError, match=match):
        VTWaveform.from_table("rising", {"r_fixture": 50, "v_fixture": 0}, rows)


def test_iv_na_cells_left_out_of_their_corner():
    """``NA`` marks one cell (IBIS 8.0 p.88): that row is left out of that corner's trace, not drawn at typ."""
    curve = IVCurve.from_table("pulldown", [(0.0, [0.0, None, 0.0]), (0.5, [0.01, 0.008, None]), (1.0, [0.02, 0.016, 0.024])])
    assert list(curve.na_min) == [True, False, False] and list(curve.na_max) == [False, True, False]
    assert curve.i_min[0] == 0.0  # Calculations still get a number.
    v, i = curve.at("min", 1.8)
    assert list(v) == [0.5, 1.0] and list(i) == [0.008, 0.016]
    assert len(curve.at("typ", 1.8)[0]) == 3


def test_iv_na_columns_left_out_of_series():
    """``typ NA NA`` rows draw one trace, not three identical ones."""
    curve = IVCurve.from_table("pulldown", [(0.0, [0.0]), (1.0, [0.02])])
    assert curve.na_min.all() and curve.na_max.all()
    assert curve.has_corner("typ") and not curve.has_corner("min")
