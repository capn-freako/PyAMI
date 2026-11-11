"""Tests for the GUI-agnostic I-V curve containers and their use by ``Model``."""

import numpy as np
import pytest

from pyibisami.ibis.file import IBISModel
from pyibisami.ibis.iv import OPEN_CIRCUIT_Z, IVCurve, IVData

PULLDOWN = [(-1.8, [-10.0, -10.0, -10.0]), (0.0, [0.0, 0.0, 0.0]), (1.8, [0.036, 0.04, 0.03273]), (3.6, [10.0, 10.0, 10.0])]
PULLUP = [(v, [-i for i in iss]) for v, iss in PULLDOWN]
CLAMP = [(-1.8, [-1.0, -1.0, -1.0]), (0.0, [0.0, 0.0, 0.0]), (1.8, [0.0, 0.0, 0.0])]


@pytest.fixture
def tx_model(ibis_test_file):
    return IBISModel(ibis_test_file).model


def test_missing_min_max_default_to_typ():
    curve = IVCurve.from_table("pulldown", [(0.0, [0.0]), (1.0, [0.02])])
    np.testing.assert_array_equal(curve.i_min, curve.i_typ)
    np.testing.assert_array_equal(curve.i_max, curve.i_typ)


def test_na_currents_are_interpolated():
    """A missing (``NA``) typical current is interpolated in its own column, as is a min/max current in the
    same row; ``NA`` typical currents are allowed at all but the lowest and highest voltages
    (IBIS 8.0 Section 6.1, p.91). A min/max current missing beside a typical one is that typical value."""
    curve = IVCurve.from_table("pulldown", [
        (0.0, [0.0, 0.0, 0.0]),
        (0.9, [None, 0.02, None]),  # As some DRAM vendors' tables have it: only I(min) measured here.
        (1.8, [0.036, 0.04, 0.032]),
        (2.7, [0.05, None, None]),  # Past the last min/max values: the typical value.
    ])
    np.testing.assert_allclose(curve.i_typ, [0.0, 0.018, 0.036, 0.05])
    np.testing.assert_allclose(curve.i_min, [0.0, 0.02, 0.04, 0.05])
    np.testing.assert_allclose(curve.i_max, [0.0, 0.016, 0.032, 0.05])
    assert curve.impedance(0.5) == pytest.approx(50.0)


def test_na_currents_with_decreasing_voltages():
    curve = IVCurve.from_table("pullup", [(1.8, [-0.036, -0.04, -0.032]), (0.9, [None, None, -0.016]), (0.0, [0.0, 0.0, 0.0])])
    np.testing.assert_allclose(curve.v, [0.0, 0.9, 1.8])  # Sorted.
    np.testing.assert_allclose(curve.i_typ, [0.0, -0.018, -0.036])
    np.testing.assert_allclose(curve.i_min, [0.0, -0.02, -0.04])
    np.testing.assert_allclose(curve.i_max, [0.0, -0.016, -0.032])


def test_impedance_of_a_descending_nonlinear_table():
    """``impedance()`` used to take the top segment of a table written in decreasing voltage, wherever ``vmeas`` was."""
    rows = [(1.8, [0.1, 0.1, 0.1]), (0.9, [0.018, 0.018, 0.018]), (0.0, [0.0, 0.0, 0.0])]
    assert IVCurve.from_table("pulldown", rows).impedance(0.5) == pytest.approx(50.0)  # 0.9 V / 18 mA.


def test_unordered_rows():
    """The first/last-row rule applies to the lowest/highest voltages; a ``nan`` used to survive here."""
    curve = IVCurve.from_table("pulldown", [(0.0, [0.0]), (1.8, [0.036]), (0.9, [None])])
    np.testing.assert_allclose(curve.i_typ, [0.0, 0.018, 0.036])
    with pytest.raises(ValueError, match="lowest and highest voltages"):
        IVCurve.from_table("pulldown", [(0.0, [0.0]), (1.8, [None]), (0.9, [0.018])])


def test_na_min_max_beside_a_typical_current_is_that_typical_value():
    """``typ NA NA`` means the typical value (IBIS 8.0 Section 6.1, p.67 and p.80), not an interpolation."""
    curve = IVCurve.from_table("pulldown", [(0.0, [0.0, 0.0, 0.0]), (1.0, [0.03, None, None]), (2.0, [0.03, 0.01, 0.05])])
    np.testing.assert_allclose(curve.i_min, [0.0, 0.03, 0.01])
    np.testing.assert_allclose(curve.i_max, [0.0, 0.03, 0.05])


@pytest.mark.parametrize("rows", [
    [(0.0, [None]), (0.9, [0.018]), (1.8, [0.036])],
    [(0.0, [0.0]), (0.9, [0.018]), (1.8, [None, 0.04, 0.03])],
])
def test_na_typical_current_in_first_or_last_row(rows):
    with pytest.raises(ValueError, match="lowest and highest voltages"):
        IVCurve.from_table("pulldown", rows)


def test_too_few_points():
    with pytest.raises(ValueError, match="Insufficient"):
        IVCurve.from_table("pullup", [(0.0, [0.0, 0.0, 0.0])])


def test_impedance():
    curve = IVCurve.from_table("pulldown", PULLDOWN)
    assert curve.impedance(0.5) == pytest.approx(50.0)
    assert curve.impedance(0.5, corner="min") == pytest.approx(45.0)
    assert curve.impedance() == pytest.approx(50.0)  # Defaults to half the max. table voltage.
    assert IVCurve.from_table("gnd_clamp", CLAMP).impedance(0.5) == OPEN_CIRCUIT_Z


def test_impedance_at_table_edges():
    """The first table voltage uses the first segment (it used to wrap to the last); off the table is an error."""
    curve = IVCurve.from_table("pulldown", PULLDOWN)
    assert curve.impedance(-1.8) == pytest.approx(0.18)  # 1.8 V / 10 A.
    with pytest.raises(ValueError, match="outside the table"):
        curve.impedance(4.0)


def test_impedance_at_zero_volts():
    """0 V is a measurement point like any other, not "no ``vmeas`` given"."""
    curve = IVCurve.from_table("gnd_clamp", [(-1.0, [-0.02, -0.02, -0.02]), (0.0, [0.0, 0.0, 0.0]), (1.0, [0.1, 0.1, 0.1])])
    assert curve.impedance(0.0) == pytest.approx(50.0)  # The segment ending at 0 V.
    assert curve.impedance() == pytest.approx(10.0)  # Half the max. table voltage: the 0 to 1 V segment.


def test_ground_referenced():
    pullup = IVCurve.from_table("pullup", PULLUP).ground_referenced(1.8)
    np.testing.assert_allclose(pullup.v, [-1.8, 0.0, 1.8, 3.6])  # Still increasing, for ``impedance()``.
    np.testing.assert_allclose(pullup.i_typ, [10.0, 0.036, 0.0, -10.0])
    assert pullup.impedance(1.0) == pytest.approx(50.0)  # 1.8 V / 36 mA.
    pulldown = IVCurve.from_table("pulldown", PULLDOWN)
    assert pulldown.ground_referenced(1.8) is pulldown


def test_driver_series_exclude_clamps():
    """An I/O model's clamp tables are kept, but only its pull-up/down curves are drawn."""
    iv = IVData.from_model_dict({"pulldown": PULLDOWN, "pullup": PULLUP, "gnd_clamp": CLAMP}, 1.8)
    assert set(iv.curves) == {"pulldown", "pullup", "gnd_clamp"}
    assert iv.is_driver
    assert [s.label for s in iv.series()] == ["PD-Typ", "PD-Min", "PD-Max", "PU-Typ", "PU-Min", "PU-Max"]


def test_unused_bad_table_skipped():
    """A malformed table the model doesn't use is dropped; a required one still raises."""
    short = [(0.0, [0.0, 0.0, 0.0])]
    iv = IVData.from_model_dict({"pulldown": PULLDOWN, "pullup": PULLUP, "gnd_clamp": short}, 1.8,
                                required=("pulldown", "pullup"))
    assert set(iv.curves) == {"pulldown", "pullup"}
    with pytest.raises(ValueError):
        IVData.from_model_dict({"pulldown": short, "pullup": PULLUP}, 1.8, required=("pulldown", "pullup"))


def test_input_series():
    iv = IVData.from_model_dict({"gnd_clamp": CLAMP, "power_clamp": CLAMP}, 1.8)
    assert not iv.is_driver
    assert iv.title == "Power/GND Clamp I-V Curves"
    assert {s.side for s in iv.series()} == {"down", "up"}


def test_model_iv_data(tx_model):
    assert tx_model.zout == pytest.approx(50.0)
    assert set(tx_model.iv_data.curves) == {"pulldown", "pullup"}
    assert tx_model.iv_data.vdd == pytest.approx(1.8)



def test_model_display_traits_hold_raw_values(tx_model):
    """The viewer's read-only model traits hold the raw IBIS values (numbers, typ/min/max lists),
    and accept new ones of the same kind (they used to be ``String`` traits)."""
    assert tx_model.vmeas == pytest.approx(0.5)
    assert tx_model.vrange == pytest.approx([1.8, 1.62, 1.98])
    assert tx_model.slew > 0
    tx_model.vmeas = 0.6
    tx_model.trange = [27.0, 0.0, 100.0]
    assert tx_model.vmeas == pytest.approx(0.6)


def test_gui_views_build(ibis_test_file):
    """Every IBIS view must resolve against the traits its object exposes."""
    pytest.importorskip("chaco")
    from chaco.api import Plot

    ibis = IBISModel(ibis_test_file)
    model = ibis.model
    assert isinstance(model.plot_iv, Plot)
    assert model.plot_iv is model.plot_iv  # Built once.
    assert sorted(model.plot_iv.plots) == sorted(s.label for s in model.iv_data.series())
    for obj in (ibis, ibis.comp_, model):
        view = obj.default_traits_view()
        names = [item.name for item in _items(view.content) if item.name]
        assert names and all(obj.trait(name) is not None for name in names), names


def test_gui_input_model_view_builds():
    """An Input model's view (clamp curves; ``zin`` instead of ``zout``/``slew``) resolves, too."""
    pytest.importorskip("chaco")
    from pyibisami.ibis.model import Model

    iv = [(0.0, (0.0, 0.0, 0.0)), (0.5, (0.01, 0.008, 0.012)), (1.0, (0.02, 0.016, 0.024))]
    model = Model({"model_type": "Input", "voltage_range": [1.0, 0.9, 1.1], "gnd_clamp": iv, "power_clamp": iv})
    assert model.zin == pytest.approx(25.0)  # Two 50 Ohm clamps, in parallel.
    assert sorted(model.plot_iv.plots) == sorted(s.label for s in model.iv_data.series())
    names = [item.name for item in _items(model.default_traits_view().content) if item.name]
    assert "zin" in names and "zout" not in names
    assert all(model.trait(name) is not None for name in names), names


# 50 Ohms at Vmeas (0.5 V), also as a ``[POWER Clamp]`` (rail-relative: 1.8 - 0.5 = 1.3 V).
CLAMP_50 = [(0.0, (0.0, 0.0, 0.0)), (0.9, (0.018, 0.0144, 0.0216)), (1.8, (0.036, 0.0288, 0.0432))]
RAMP = {"rising": [2e9], "falling": [2e9], "load": 50}  # 2 V/ns.


def _model(model_type, name="m", **tables):
    from pyibisami.ibis.model import Model

    return Model({"model_type": model_type, "voltage_range": [1.8, 1.62, 1.98], "vmeas": 0.5, **tables}, name=name)


@pytest.mark.parametrize("model_type, tables, zout, slew, zin", [
    ("I/O", {"pulldown": PULLDOWN, "pullup": PULLUP, "ramp": RAMP, "gnd_clamp": CLAMP_50, "power_clamp": CLAMP_50},
     50.0, 2.0, 25.0),
    ("3-state", {"pulldown": PULLDOWN, "pullup": PULLUP, "ramp": RAMP}, 50.0, 2.0, None),
    ("Open_drain", {"pulldown": PULLDOWN, "ramp": RAMP}, 50.0, 2.0, None),  # One-sided: the pull-down's impedance.
    ("Open_source", {"pullup": PULLUP, "ramp": RAMP}, 50.0, 2.0, None),
    ("I/O_open_drain", {"pulldown": PULLDOWN, "ramp": RAMP, "gnd_clamp": CLAMP_50}, 50.0, 2.0, 50.0),
    ("I/O", {"pulldown": PULLDOWN, "pullup": PULLUP, "ramp": RAMP}, 50.0, 2.0, 2e6),  # No clamps: NO_CLAMP_Z.
    ("Output_ECL", {"pulldown": PULLDOWN, "pullup": PULLUP, "ramp": RAMP}, None, None, None),  # Not supported yet.
    ("Terminator", {"gnd_clamp": CLAMP_50}, None, None, None),
])
def test_analog_values_per_model_type(model_type, tables, zout, slew, zin):
    """``zout``/``slew``/``zin`` are numbers where the Model_type and its data support them, else ``None``."""
    model = _model(model_type, **tables)
    for name, expected in (("zout", zout), ("slew", slew), ("zin", zin)):
        value = getattr(model, name)
        assert value is None if expected is None else value == pytest.approx(expected), (name, value)


def test_missing_driver_data_warns_without_failing(caplog):
    """A ``3-state`` model without I-V tables or ``[Ramp]`` still loads (as before), with one warning."""
    with caplog.at_level("WARNING", logger="pyibisami.ibis.model"):
        model = _model("3-state", name="oe_buf")
    assert (model.zout, model.slew, model.zin, model.iv_data) == (None, None, None, None)
    assert len(caplog.records) == 1
    assert all(s in caplog.text for s in ("oe_buf", "[Pulldown]", "[Pullup]", "[Ramp]"))


def test_tables_that_dont_reach_vmeas(caplog):
    """A table not covering Vmeas loads: an off clamp counts as absent; an unknown ``zout`` is ``None`` (warning).

    E.g. - a ``[POWER Clamp]`` given only for -Vcc to 0 V (where it conducts), with Vmeas = 0.5 V.
    """
    from pyibisami.ibis.model import NO_CLAMP_Z

    power_clamp_on_only = [(-1.8, [0.1, 0.1, 0.1]), (0.0, [0.0, 0.0, 0.0])]
    model = _model("I/O", pulldown=PULLDOWN, pullup=PULLUP, ramp=RAMP, gnd_clamp=CLAMP_50,
                   power_clamp=power_clamp_on_only)
    assert model.zin == pytest.approx(50.0 * NO_CLAMP_Z / (50.0 + NO_CLAMP_Z))
    with caplog.at_level("WARNING", logger="pyibisami.ibis.model"):
        model = _model("Open_drain", name="short_pd", pulldown=PULLDOWN[:2], ramp=RAMP)  # Table ends at 0 V.
    assert model.zout is None and model.slew == pytest.approx(2.0)
    assert "short_pd" in caplog.text and "outside the table" in caplog.text


def test_rail_relative_curves_are_read_at_the_pin_voltage():
    """``[Pullup]``/``[POWER Clamp]`` voltages are Vdd - Vpin; they used to be read at Vpin itself."""
    from pyibisami.ibis.model import Model

    # Rail-relative: 100 Ohms from 0 to 1 V, then 50 Ohms; Vmeas = 0.5 V is 1.3 V rail-relative (Vdd = 1.8 V).
    pullup = [(0.0, [0.0, 0.0, 0.0]), (1.0, [-0.01, -0.01, -0.01]), (1.8, [-0.026, -0.026, -0.026])]
    assert _model("Open_source", pullup=pullup, ramp=RAMP).zout == pytest.approx(50.0)
    # A VDDQ-terminated ODT (DDR4/5 POD) in [POWER Clamp]: Vdd = 1.2 V, Vmeas = 0.84 V, i.e. - 0.36 V rail-relative.
    odt = [(0.0, [0.0, 0.0, 0.0]), (0.5, [-0.01, -0.01, -0.01]), (1.2, [-0.017, -0.017, -0.017])]  # 50, then 100 Ohms.
    model = Model({"model_type": "Input", "voltage_range": [1.2, 1.14, 1.26], "vmeas": 0.84,
                   "add_submodel": [("odt", "Non-Driving")]})
    assert model.apply_submodels({"odt": {"submodel_type": "Dynamic_clamp", "power_clamp": odt}}) == []
    assert model.zin == pytest.approx(50.0, rel=1e-3)  # In parallel with NO_CLAMP_Z.


# 50 Ohms below 0.6 V, 100 Ohms above.
BENT_CLAMP = [(0.0, [0.0, 0.0, 0.0]), (0.6, [0.012, 0.012, 0.012]), (2.0, [0.026, 0.026, 0.026])]


@pytest.mark.parametrize("params, zin", [
    ({"vinl": [0.2, 0.15, 0.25], "vinh": [0.6, 0.55, 0.65]}, 50.0),  # Typ/min/max thresholds: their typical midpoint.
    ({"vinl": [0.6, 0.55, 0.65], "vinh": [1.0, 0.95, 1.05]}, 100.0),
    ({"vmeas": [0.4, 0.3, 0.5]}, 50.0),  # A typ/min/max Vmeas: its typical value.
    ({}, 50.0),  # Neither: Vdd / 2 (it used to be each table's own max. voltage / 2: 1 V here).
])
def test_input_operating_point(params, zin):
    from pyibisami.ibis.model import Model

    model = Model({"model_type": "Input", "voltage_range": [1.0, 0.9, 1.1], "gnd_clamp": BENT_CLAMP, **params})
    assert model.zin == pytest.approx(zin)


def test_unusable_required_iv_table_is_a_lookup_error():
    """``Model`` reports an unusable required I-V table like a missing one, so the parser catches it."""
    with pytest.raises(LookupError, match="Unusable I-V table"):
        _model("Output", pulldown=[(0.0, [None]), (1.8, [0.036])], pullup=PULLUP, ramp=RAMP)


def test_output_still_requires_driver_data():
    with pytest.raises(LookupError, match="Ramp"):
        _model("Output", pulldown=PULLDOWN, pullup=PULLUP)
    with pytest.raises(LookupError, match="I-V"):
        _model("I/O", pulldown=PULLDOWN, ramp=RAMP)


def test_gui_io_model_view_shows_both_impedances():
    pytest.importorskip("chaco")
    model = _model("I/O", pulldown=PULLDOWN, pullup=PULLUP, ramp=RAMP, gnd_clamp=CLAMP_50, power_clamp=CLAMP_50)
    names = [item.name for item in _items(model.default_traits_view().content) if item.name]
    assert {"zout", "slew", "zin"} <= set(names)
    assert all(model.trait(name) is not None for name in names), names


def _items(group):
    from traitsui.api import Group

    for elem in group.content:
        if isinstance(elem, Group):
            yield from _items(elem)
        else:
            yield elem
