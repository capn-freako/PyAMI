"""Traits/UI viewers for IBIS model constituents.

Kept separate from ``pyibisami.ibis.model``, so that IBIS parsing doesn't require the
(optional) GUI dependencies, which are installed via: ``pip install "pyibis-ami[gui]"``.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   October 9, 2026

Copyright (c) 2026 by David Banas; All rights reserved World wide.
"""

from traits.api import Any, Float, HasTraits, String, Trait

from pyibisami.common import require_gui

with require_gui():
    from chaco.api import ArrayPlotData, Plot
    from enable.component_editor import ComponentEditor
    from traitsui.api import Group, Item, ModalButtons, View

from .model import Component, Model

# (I-V curve key, plot name prefix, color), per model type.
_IV_PLOT_CURVES = {
    "output": [("pulldown", "PD", "blue"), ("pullup", "PU", "red")],
    "input": [("gnd_clamp", "PD", "blue"), ("power_clamp", "PU", "red")],
}
_IV_PLOT_LABELS = {
    "output": ("Pull-Up/Down I-V Curves", "Vout (V)", "Iout (A)"),
    "input": ("Power/GND Clamp I-V Curves", "Vin (V)", "Iin (A)"),
}


def _iv_kind(model: Model) -> str:
    "Which I-V curves (and impedance) a model has: 'output', 'input', or '' (neither)."
    mtype = model.mtype.lower()
    if mtype in ("output", "i/o"):
        return "output"
    if mtype == "input":
        return "input"
    return ""


def make_iv_plot(model: Model) -> Plot:
    """
    Build a Chaco plot of a model's I-V curves.

    Args:
        model: The IBIS model, whose ``iv_curves`` are to be plotted.

    Returns:
        The I-V curves plot.
    """

    kind = _iv_kind(model)
    if not kind:
        raise ValueError(f"Model type '{model.mtype}' has no I-V curves to plot.")
    plotdata = ArrayPlotData()
    plot_iv = Plot(plotdata)  # , padding_left=75)
    # The 'line_style' trait of a LinePlot instance must be 'dash' or 'dot dash' or 'dot' or 'long dash' or 'solid'.
    for key, prefix, color in _IV_PLOT_CURVES[kind]:
        if key not in model.iv_curves:
            continue
        for col, val in model.iv_curves[key].items():
            plotdata.set_data(f"{key}_{col}", val)
        for col, suffix, line_style in [("ityps", "Typ", "solid"), ("imins", "Min", "dot"), ("imaxs", "Max", "dash")]:
            plot_iv.plot(
                (f"{key}_vs", f"{key}_{col}"),
                type="line", color=color, line_style=line_style, name=f"{prefix}-{suffix}")
    title, index_title, value_title = _IV_PLOT_LABELS[kind]
    plot_iv.title = title
    plot_iv.index_axis.title = index_title
    plot_iv.value_axis.title = value_title
    plot_iv.index_range.low_setting = 0
    plot_iv.index_range.high_setting = model.vrange[0]
    plot_iv.value_range.low_setting = 0
    plot_iv.value_range.high_setting = 0.1
    plot_iv.legend.visible = True
    plot_iv.legend.align = "ul"
    return plot_iv


class ComponentView(HasTraits):
    """GUI viewer for a ``Component``."""

    manufacturer = String()
    package = String()

    def __init__(self, component: Component):
        """
        Args:
            component: The IBIS component to view.
        """

        super().__init__()
        self._component = component
        self.manufacturer = str(component.manufacturer)
        self.package = str(component.package)
        pins = component.pins
        self.add_trait("pin", Trait(component._pin_name, pins))  # pylint: disable=protected-access

    def _pin_changed(self, new_value):
        self._component._pin_name = new_value  # pylint: disable=protected-access

    def default_traits_view(self):
        "Default Traits/UI view definition."
        return View(
            Group(
                Item("manufacturer", label="Manufacturer", style="readonly"),
                Item("package", label="Package", style="readonly"),
                Item("pin", label="Pin"),
                label="Component",
                show_border=True,
            ),
            resizable=False,
            buttons=ModalButtons,
            title="PyBERT IBIS Component Viewer",
            id="pyibisami.ibis_parser.Component",
        )


class ModelView(HasTraits):  # pylint: disable=too-many-instance-attributes
    """GUI viewer for a ``Model``."""

    model_type = String()
    c_comp = String()
    cref = String()
    vref = String()
    vmeas = String()
    rref = String()
    trange = String()
    vrange = String()
    zout = Float()  # (Numeric, for the views' ``format_str``.)
    slew = Float()
    zin = Float()
    plot_iv = Any()

    def __init__(self, model: Model):
        """
        Args:
            model: The IBIS model to view.
        """

        super().__init__()
        self._kind = _iv_kind(model)
        self.model_type = str(model.mtype)
        self.c_comp = str(model.ccomp)
        self.cref = str(model.cref)
        self.vref = str(model.vref)
        self.vmeas = str(model.vmeas)
        self.rref = str(model.rref)
        self.trange = str(model.trange)
        self.vrange = str(model.vrange)
        if self._kind == "output":
            self.zout = model.zout
            self.slew = model.slew
        elif self._kind == "input":
            self.zin = model.zin
        if self._kind:
            self.plot_iv = make_iv_plot(model)

    def default_traits_view(self):
        "Default Traits/UI view definition."
        content = [
            Group(
                Item("model_type", label="Model type", style="readonly"),
                Item("c_comp", label="Ccomp", style="readonly"),
                Item("trange", label="Temperature Range", style="readonly"),
                Item("vrange", label="Voltage Range", style="readonly"),
                Group(
                    Item("cref", label="Cref", style="readonly"),
                    Item("vref", label="Vref", style="readonly"),
                    Item("vmeas", label="Vmeas", style="readonly"),
                    Item("rref", label="Rref", style="readonly"),
                    orientation="horizontal",
                ),
                label="Model",
                show_border=True,
            ),
        ]
        if self._kind == "output":
            content.append(Item("zout", label="Impedance (Ohms)", style="readonly", format_str="%4.1f"))
            content.append(Item("slew", label="Slew Rate (V/ns)", style="readonly", format_str="%4.1f"))
        elif self._kind == "input":
            content.append(Item("zin", label="Impedance (Ohms)", style="readonly", format_str="%4.1f"))
        if self._kind:
            content.append(Item("plot_iv", editor=ComponentEditor(), show_label=False))
        view = View(
            resizable=False,
            buttons=ModalButtons,
            title="PyBERT IBIS Model Viewer",
            id="pyibisami.ibis_parser.Model",
        )
        view.set_content(content)
        return view
