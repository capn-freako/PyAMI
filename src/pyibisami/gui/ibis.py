"""
Traits/UI views for the IBIS model classes: ``Component``, ``Model`` & ``IBISModel``.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   November 1, 2019

Copyright (c) 2019 by David Banas; All rights reserved World wide.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chaco.api import ArrayPlotData, Plot
from enable.component_editor import ComponentEditor
from traits.observation.exceptions import NotifierNotFound
from traitsui.api import Group, HGroup, Item, ModalButtons, VGroup, View, spring
from traitsui.message import message

if TYPE_CHECKING:
    from ..ibis.file import IBISModel
    from ..ibis.iv import IVData
    from ..ibis.model import Component, Model

# Chaco styling of the toolkit-neutral ``IVSeries`` hints.
SIDE_COLORS = {"down": "blue", "up": "red"}
CORNER_LINE_STYLES = {"typ": "solid", "min": "dot", "max": "dash"}


def make_iv_plot(iv_data: IVData) -> Plot:
    """
    Builds a Chaco plot of a model's I-V curves.

    Args:
        iv_data: The I-V curves to plot.

    Returns:
        The Chaco ``Plot``.
    """
    plotdata = ArrayPlotData()
    plot_iv = Plot(plotdata)
    for n, series in enumerate(iv_data.series()):
        plotdata.set_data(f"v{n}", series.v)
        plotdata.set_data(f"i{n}", series.i)
        plot_iv.plot(
            (f"v{n}", f"i{n}"), type="line", name=series.label,
            color=SIDE_COLORS[series.side], line_style=CORNER_LINE_STYLES[series.corner])
    plot_iv.title = iv_data.title
    plot_iv.index_axis.title = iv_data.v_label
    plot_iv.value_axis.title = iv_data.i_label
    plot_iv.index_range.low_setting = 0
    plot_iv.index_range.high_setting = iv_data.vdd
    plot_iv.value_range.low_setting = 0
    plot_iv.value_range.high_setting = 0.1
    plot_iv.legend.visible = True
    plot_iv.legend.align = "ul"
    return plot_iv


def make_component_view(comp: Component) -> View:  # pylint: disable=unused-argument
    "Builds the ``Component`` viewer."
    return View(
        Group(
            Item("manufacturer", label="Manufacturer", style="readonly"),
            Item("package", label="Package", style="readonly"),
            Item("_pin", label="Pin"),
            label="Component",
            show_border=True,
        ),
        resizable=False,
        buttons=ModalButtons,
        title="IBIS Component Viewer",
        id="pyibisami.ibis_parser.Component",
    )


def make_model_view(model: Model) -> View:
    "Builds the ``Model`` viewer."
    content: list[Item | Group] = [
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
    mtype = model.mtype.lower()
    if mtype in ("output", "i/o"):
        content.append(Item("zout", label="Impedance (Ohms)", style="readonly", format_str="%4.1f"))
        content.append(Item("slew", label="Slew Rate (V/ns)", style="readonly", format_str="%4.1f"))
    elif mtype == "input":
        content.append(Item("zin", label="Impedance (Ohms)", style="readonly", format_str="%4.1f"))
    if model.iv_data is not None:
        content.append(Item("plot_iv", editor=ComponentEditor(), show_label=False))
    view = View(
        resizable=False,
        buttons=ModalButtons,
        title="IBIS Model Viewer",
        id="pyibisami.ibis_parser.Model",
    )
    view.set_content(content)
    return view


def make_ibis_file_view(ibis: IBISModel) -> View:  # pylint: disable=unused-argument
    "Builds the ``IBISModel`` component/pin/model selector."
    return View(
        VGroup(
            HGroup(
                Item("file_name", label="File name", style="readonly"),
                spring,
                Item("file_rev", label="rev", style="readonly"),
            ),
            HGroup(
                Item("ibis_ver", label="IBIS ver", style="readonly"),
                spring,
                Item("date", label="Date", style="readonly"),
            ),
            HGroup(
                Item("comp", label="Component"),
                Item("pin", label="Pin"),
                Item("mod", label="Model"),
            ),
        ),
        resizable=False,
        buttons=ModalButtons,
        title="IBIS Model Selector",
        id="pyibisami_ibis_model_selector",
    )


def show_alerts(ibis: IBISModel) -> None:
    """
    Pop up a dialog for each ``alert`` the model fires from now on.

    Calling it again for the same model doesn't add a second dialog.
    """
    try:
        ibis.observe(_alert_popup, "alert", remove=True)
    except NotifierNotFound:
        pass
    ibis.observe(_alert_popup, "alert")


def _alert_popup(event) -> None:
    message(event.new, "PyAMI Alert")
