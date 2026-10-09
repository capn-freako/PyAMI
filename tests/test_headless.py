"""Headless (no GUI dependencies) use of PyIBIS-AMI; see Issue #95."""

import subprocess
import sys

import numpy as np
import pytest

from pyibisami.ami.parser import AMIParamConfigurator
from pyibisami.ibis.file import IBISModel

AMI_CONTENTS = r"""(example_rx
    (Reserved_Parameters
         (Init_Returns_Impulse (Usage Info) (Type Boolean) (Value True) (Description "x"))
         (GetWave_Exists (Usage Info) (Type Boolean) (Value False) (Description "x"))
    )
    (Model_Specific
         (enable (Usage In) (Type Boolean) (Value True) (Description "Top-level flag."))
         (ctle_mode (Usage In) (Type Integer) (List 0 1 2) (Description "Prefix-grouped list."))
         (ctle_level (Usage InOut) (Type Float) (Range 0.5 0.0 1.0) (Description "Prefix-grouped range."))
         (dfe_out (Usage Out) (Type Float) (Value 0.0) (Description "Not configurable."))
         (tx_preset
             (Description "A described group.")
             (coeffs
                 (main (Usage In) (Type Float) (Range 0.5 0.0 1.0) (Description "Nested."))
             )
         )
    )
)
"""
GUI_MODULES = ("chaco", "enable", "kiwisolver", "traitsui", "pyface", "PySide6", "PyQt5", "PyQt6", "matplotlib")
CORE_MODULES = ("pyibisami.ibis.parser", "pyibisami.ibis.file", "pyibisami.ami.parser", "pyibisami.ami.model")


@pytest.mark.parametrize("module", CORE_MODULES)
def test_core_import_pulls_in_no_gui(module):
    """Importing a parsing/modeling module mustn't import any GUI/plotting package.

    (Run in a fresh interpreter, since this one may already have them loaded.)
    """
    code = (
        f"import sys, {module}\n"
        f"print(sorted({{m.split('.')[0] for m in sys.modules}} & set({GUI_MODULES!r})))"
    )
    rslt = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert rslt.stdout.strip() == "[]"


def test_ibis_model_data_without_gui(ibis_test_file):
    """The electrical model data is available without building any GUI."""
    ibis = IBISModel(ibis_test_file, debug=False, gui=False)
    model = ibis.model
    assert model.mtype.lower() == "output"
    assert model.zout > 0
    assert model.slew > 0
    assert set(model.iv_curves) == {"pulldown", "pullup"}
    for curve in model.iv_curves.values():
        assert set(curve) == {"vs", "ityps", "imins", "imaxs"}
        assert len({len(col) for col in curve.values()}) == 1
    # Pull-up voltages are made ground-relative.
    np.testing.assert_allclose(
        model.iv_curves["pullup"]["vs"],
        model.vrange[0] - np.array([v for v, _ in model._subDict["pullup"]]),  # pylint: disable=protected-access
    )


def test_component_pin_without_gui(ibis_test_file):
    "``Component.pin`` defaults to the first pin, without a GUI."
    ibis = IBISModel(ibis_test_file, debug=False, gui=False)
    comp = ibis.comp_
    assert comp.pin == comp.pins[next(iter(comp.pins))]


class TestGui:
    "The optional GUI layer, when its dependencies are installed."

    @pytest.fixture(autouse=True)
    def _needs_gui(self):
        pytest.importorskip("chaco")
        pytest.importorskip("traitsui")

    def test_model_view(self, ibis_test_file):
        from pyibisami.ibis.gui import ModelView  # pylint: disable=import-outside-toplevel

        model = IBISModel(ibis_test_file, debug=False, gui=False).model
        view = ModelView(model)
        assert float(view.zout) == model.zout
        assert len(view.plot_iv.plots) == 6  # PD/PU x Typ/Min/Max
        assert view.default_traits_view() is not None
        assert len(model.plot_iv.plots) == 6  # Backward-compatible attribute.

    def test_component_view_tracks_pin(self, ibis_test_file):
        from pyibisami.ibis.gui import ComponentView  # pylint: disable=import-outside-toplevel

        comp = IBISModel(ibis_test_file, debug=False, gui=False).comp_
        view = ComponentView(comp)
        last_pin = list(comp.pins)[-1]
        view.pin = last_pin
        assert comp.pin == comp.pins[last_pin]

    def test_ibis_model_view(self, ibis_test_file):
        ibis = IBISModel(ibis_test_file, debug=False, gui=False)
        assert ibis.default_traits_view() is not None

    def test_ami_view_items_match_traits(self):
        "Every configurator GUI item names a trait ``make_param_traits()`` registered, and vice versa."
        from traitsui.api import Group, Item  # pylint: disable=import-outside-toplevel

        def item_names(content):
            for x in content:
                if isinstance(x, Group):
                    yield from item_names(x.content)
                elif isinstance(x, Item) and x.name:
                    yield x.name

        cfg = AMIParamConfigurator(AMI_CONTENTS)
        view = cfg.default_traits_view()
        names = set(item_names(view.content.content))
        assert names == set(cfg._param_trait_names)  # pylint: disable=protected-access
        assert all(cfg.trait(name) is not None for name in names)
