"""Classes for encapsulating IBIS model constituents.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   November 1, 2019

For information regarding the IBIS modeling standard, visit:
https://ibis.org/

Copyright (c) 2019 by David Banas; All rights reserved World wide.
"""

import numpy as np
from chaco.api import ArrayPlotData, Plot
from enable.component_editor import ComponentEditor
from traits.api import HasTraits, String, Trait
from traitsui.api import Group, Item, ModalButtons, View


class Component(HasTraits):
    """Encapsulation of a particular component from an IBIS model file."""

    def __init__(self, subDict):
        """
        Args:
            subDict(dict): Dictionary of [Component] sub-keywords/params.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super().__init__()

        # Stash the sub-keywords/parameters.
        self._subDict = subDict

        # Fetch available keyword/parameter definitions.
        def maybe(name):
            return subDict[name] if name in subDict else None

        self._mfr = maybe("manufacturer")
        self._pkg = maybe("package")
        self._pins = maybe("pin")
        self._diffs = maybe("diff_pin")

        # Check for the required keywords.
        if not self._mfr:
            raise LookupError("Missing [Manufacturer]!")
        if not self._pkg:
            print(self._mfr)
            raise LookupError("Missing [Package]!")
        if not self._pins:
            raise LookupError("Missing [Pin]!")

        # Set up the GUI.
        self.add_trait("manufacturer", String(self._mfr))
        self.add_trait("package", String(self._pkg))
        self.add_trait("_pin", Trait(list(self._pins)[0], self._pins))
        self._content = [
            Group(
                Item("manufacturer", label="Manufacturer", style="readonly"),
                Item("package", label="Package", style="readonly"),
                Item("_pin", label="Pin"),
                label="Component",
                show_border=True,
            ),
        ]

    def __str__(self):
        res = "Manufacturer:\t" + self._mfr + "\n"
        res += "Package:     \t" + str(self._pkg) + "\n"
        res += "Pins:\n"
        for pname in self._pins:
            res += "    " + pname + ":\t" + str(self._pins[pname]) + "\n"
        return res

    def __call__(self):
        self.edit_traits()

    def default_traits_view(self):
        "Default Traits/UI view definition."
        view = View(
            resizable=False,
            buttons=ModalButtons,
            title="PyBERT IBIS Component Viewer",
            id="pyibisami.ibis_parser.Component",
        )
        view.set_content(self._content)
        return view

    @property
    def pin(self):
        """The pin selected most recently by the user.

        Returns the first pin in the list, if the user hasn't made a
        selection yet.
        """
        return self._pin_

    @property
    def pins(self):
        "The list of component pins."
        return self._pins


class Model(HasTraits):  # pylint: disable=too-many-instance-attributes
    """Encapsulation of a particular I/O model from an IBIS model file."""

    def __init__(self, subDict):  # pylint: disable=too-many-locals,too-many-statements,too-many-branches
        """
        Args:
            subDict (dict): Dictionary of sub-keywords/params.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super().__init__()

        # Stash the sub-keywords/parameters.
        self._subDict = subDict

        # Fetch available keyword/parameter definitions.
        def maybe(name):
            return subDict[name] if name in subDict else None

        self._mtype = maybe("model_type")
        self._ccomp = maybe("c_comp")
        self._cref = maybe("cref")
        self._vref = maybe("vref")
        self._vmeas = maybe("vmeas")
        self._rref = maybe("rref")
        self._trange = maybe("temperature_range")
        self._vrange = maybe("voltage_range")
        self._ramp = maybe("ramp")

        # Check for the required keywords.
        if not self._mtype:
            raise LookupError("Missing Model_type!")
        if not self._vrange:
            raise LookupError("Missing [Voltage Range]!")

        def proc_iv(xs):
            """Process an I/V table."""
            if len(xs) < 2:
                raise ValueError("Insufficient number of I-V data points!")
            try:
                vs, iss = zip(*(xs))  # Idiomatic Python for ``unzip``.
            except Exception as exc:
                raise ValueError(f"xs: {xs}") from exc
            ityps, imins, imaxs = zip(*iss)
            vmeas = self._vmeas

            def calcZ(x):
                (vs, ivals) = x
                if vmeas:
                    ix = np.where(np.array(vs) >= vmeas)[0][0]
                else:
                    ix = np.where(np.array(vs) >= max(vs) / 2)[0][0]
                try:
                    return abs((vs[ix] - vs[ix - 1]) / (ivals[ix] - ivals[ix - 1]))
                except ZeroDivisionError:
                    return 1e7  # Use 10 MOhms in place of infinity.

            zs = map(calcZ, zip([vs, vs, vs], [ityps, imins, imaxs]))
            return vs, ityps, imins, imaxs, zs

        # Infer impedance and/or rise/fall time, as per model type.
        mtype = self._mtype.lower()
        if mtype in ("output", "i/o"):
            if "pulldown" not in subDict or "pullup" not in subDict:
                raise LookupError("Missing I-V curves!")
            plotdata = ArrayPlotData()
            pd_vs, pd_ityps, pd_imins, pd_imaxs, pd_zs = proc_iv(subDict["pulldown"])
            pu_vs, pu_ityps, pu_imins, pu_imaxs, pu_zs = proc_iv(subDict["pullup"])
            pu_vs = self._vrange[0] - np.array(pu_vs)  # Correct for Vdd-relative pull-up voltages.
            pu_ityps = -np.array(pu_ityps)  # Correct for current sense, for nicer plot.
            pu_imins = -np.array(pu_imins)
            pu_imaxs = -np.array(pu_imaxs)
            self._zout = (list(pd_zs)[0] + list(pu_zs)[0]) / 2
            plotdata.set_data("pd_vs", pd_vs)
            plotdata.set_data("pd_ityps", pd_ityps)
            plotdata.set_data("pd_imins", pd_imins)
            plotdata.set_data("pd_imaxs", pd_imaxs)
            plotdata.set_data("pu_vs", pu_vs)
            plotdata.set_data("pu_ityps", pu_ityps)
            plotdata.set_data("pu_imins", pu_imins)
            plotdata.set_data("pu_imaxs", pu_imaxs)
            plot_iv = Plot(plotdata)  # , padding_left=75)
            # The 'line_style' trait of a LinePlot instance must be 'dash' or 'dot dash' or 'dot' or 'long dash' or 'solid'.
            plot_iv.plot(("pd_vs", "pd_ityps"), type="line", color="blue", line_style="solid", name="PD-Typ")
            plot_iv.plot(("pd_vs", "pd_imins"), type="line", color="blue", line_style="dot", name="PD-Min")
            plot_iv.plot(("pd_vs", "pd_imaxs"), type="line", color="blue", line_style="dash", name="PD-Max")
            plot_iv.plot(("pu_vs", "pu_ityps"), type="line", color="red", line_style="solid", name="PU-Typ")
            plot_iv.plot(("pu_vs", "pu_imins"), type="line", color="red", line_style="dot", name="PU-Min")
            plot_iv.plot(("pu_vs", "pu_imaxs"), type="line", color="red", line_style="dash", name="PU-Max")
            plot_iv.title = "Pull-Up/Down I-V Curves"
            plot_iv.index_axis.title = "Vout (V)"
            plot_iv.value_axis.title = "Iout (A)"
            plot_iv.index_range.low_setting = 0
            plot_iv.index_range.high_setting = self._vrange[0]
            plot_iv.value_range.low_setting = 0
            plot_iv.value_range.high_setting = 0.1
            plot_iv.legend.visible = True
            plot_iv.legend.align = "ul"
            self.plot_iv = plot_iv

            if not self._ramp:
                raise LookupError("Missing [Ramp]!")
            ramp = subDict["ramp"]
            self._slew = (ramp["rising"][0] + ramp["falling"][0]) / 2e9  # (V/ns)
        elif mtype == "input":
            if "gnd_clamp" not in subDict and "power_clamp" not in subDict:
                raise LookupError("Missing clamp curves!")

            plotdata = ArrayPlotData()

            if "gnd_clamp" in subDict:
                gc_vs, gc_ityps, gc_imins, gc_imaxs, gc_zs = proc_iv(subDict["gnd_clamp"])
                gc_z = list(gc_zs)[0]  # Use typical value for Zin calc.
                plotdata.set_data("gc_vs", gc_vs)
                plotdata.set_data("gc_ityps", gc_ityps)
                plotdata.set_data("gc_imins", gc_imins)
                plotdata.set_data("gc_imaxs", gc_imaxs)

            if "power_clamp" in subDict:
                pc_vs, pc_ityps, pc_imins, pc_imaxs, pc_zs = proc_iv(subDict["power_clamp"])
                pc_z = list(pc_zs)[0]
                pc_vs = self._vrange[0] - np.array(pc_vs)  # Correct for Vdd-relative pull-up voltages.
                pc_ityps = -np.array(pc_ityps)  # Correct for current sense, for nicer plot.
                pc_imins = -np.array(pc_imins)
                pc_imaxs = -np.array(pc_imaxs)
                plotdata.set_data("pc_vs", pc_vs)
                plotdata.set_data("pc_ityps", pc_ityps)
                plotdata.set_data("pc_imins", pc_imins)
                plotdata.set_data("pc_imaxs", pc_imaxs)

            plot_iv = Plot(plotdata)  # , padding_left=75)
            # The 'line_style' trait of a LinePlot instance must be 'dash' or 'dot dash' or 'dot' or 'long dash' or 'solid'.
            if "gnd_clamp" in subDict:
                plot_iv.plot(("gc_vs", "gc_ityps"), type="line", color="blue", line_style="solid", name="PD-Typ")
                plot_iv.plot(("gc_vs", "gc_imins"), type="line", color="blue", line_style="dot", name="PD-Min")
                plot_iv.plot(("gc_vs", "gc_imaxs"), type="line", color="blue", line_style="dash", name="PD-Max")
            if "power_clamp" in subDict:
                plot_iv.plot(("pc_vs", "pc_ityps"), type="line", color="red", line_style="solid", name="PU-Typ")
                plot_iv.plot(("pc_vs", "pc_imins"), type="line", color="red", line_style="dot", name="PU-Min")
                plot_iv.plot(("pc_vs", "pc_imaxs"), type="line", color="red", line_style="dash", name="PU-Max")
            plot_iv.title = "Power/GND Clamp I-V Curves"
            plot_iv.index_axis.title = "Vin (V)"
            plot_iv.value_axis.title = "Iin (A)"
            plot_iv.index_range.low_setting = 0
            plot_iv.index_range.high_setting = self._vrange[0]
            plot_iv.value_range.low_setting = 0
            plot_iv.value_range.high_setting = 0.1
            plot_iv.legend.visible = True
            plot_iv.legend.align = "ul"
            self.plot_iv = plot_iv

            if "gnd_clamp" in subDict and "power_clamp" in subDict:
                # Parallel combination, as both clamps are always active.
                self._zin = (gc_z * pc_z) / (gc_z + pc_z)  # pylint: disable=possibly-used-before-assignment
            elif "gnd_clamp" in subDict:
                self._zin = gc_z
            else:
                self._zin = pc_z

        # Separate AMI executables by OS.
        def is64(x):
            ((_, b), _) = x
            return int(b) == 64

        def isWin(x):
            ((os, _), _) = x
            return os.lower() == "windows"

        def partition(p, xs):
            ts, fs = [], []
            for x in xs:
                if p(x):
                    ts.append(x)
                else:
                    fs.append(x)
            return ts, fs

        def getFiles(x):
            if x:
                ((_, _), fs) = x[0]
                return fs
            return []

        def splitExecs(fs):
            wins, lins = partition(isWin, fs)
            return (getFiles(wins), getFiles(lins))

        self._exec32Wins, self._exec32Lins = [], []
        self._exec64Wins, self._exec64Lins = [], []
        if "algorithmic_model" in subDict:
            execs = subDict["algorithmic_model"]
            exec64s, exec32s = partition(is64, execs)
            self._exec32Wins, self._exec32Lins = splitExecs(exec32s)
            self._exec64Wins, self._exec64Lins = splitExecs(exec64s)

        # Set up the GUI.
        self.add_trait("model_type", String(self._mtype))
        self.add_trait("c_comp", String(self._ccomp))
        self.add_trait("cref", String(self._cref))
        self.add_trait("vref", String(self._vref))
        self.add_trait("vmeas", String(self._vmeas))
        self.add_trait("rref", String(self._rref))
        self.add_trait("trange", String(self._trange))
        self.add_trait("vrange", String(self._vrange))
        if mtype in ("output", "i/o"):
            self.add_trait("zout", String(self._zout))
            self.add_trait("slew", String(self._slew))
        elif mtype == "input":
            self.add_trait("zin", String(self._zin))
        self._content = [
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
        if mtype in ("output", "i/o"):
            self._content.append(Item("zout", label="Impedance (Ohms)", style="readonly", format_str="%4.1f"))
            self._content.append(Item("slew", label="Slew Rate (V/ns)", style="readonly", format_str="%4.1f"))
            self._content.append(Item("plot_iv", editor=ComponentEditor(), show_label=False))
        elif mtype == "input":
            self._content.append(Item("zin", label="Impedance (Ohms)", style="readonly", format_str="%4.1f"))
            self._content.append(Item("plot_iv", editor=ComponentEditor(), show_label=False))

    def __str__(self):
        res = "Model Type:\t" + self._mtype + "\n"
        res += "C_comp:    \t" + str(self._ccomp) + "\n"
        res += "Cref:      \t" + str(self._cref) + "\n"
        res += "Vref:      \t" + str(self._vref) + "\n"
        res += "Vmeas:     \t" + str(self._vmeas) + "\n"
        res += "Rref:      \t" + str(self._rref) + "\n"
        res += "Temperature Range:\t" + str(self._trange) + "\n"
        res += "Voltage Range:    \t" + str(self._vrange) + "\n"
        if "algorithmic_model" in self._subDict:
            res += "Algorithmic Model:\n" + "\t32-bit:\n"
            if self._exec32Lins:
                res += "\t\tLinux: " + str(self._exec32Lins) + "\n"
            if self._exec32Wins:
                res += "\t\tWindows: " + str(self._exec32Wins) + "\n"
            res += "\t64-bit:\n"
            if self._exec64Lins:
                res += "\t\tLinux: " + str(self._exec64Lins) + "\n"
            if self._exec64Wins:
                res += "\t\tWindows: " + str(self._exec64Wins) + "\n"
        return res

    def __call__(self):
        self.edit_traits(kind="livemodal")

    def default_traits_view(self):
        "Default Traits/UI view definition."
        view = View(
            resizable=False,
            buttons=ModalButtons,
            title="PyBERT IBIS Model Viewer",
            id="pyibisami.ibis_parser.Model",
        )
        view.set_content(self._content)
        return view

    @property
    def zout(self):
        "The driver impedance."
        return self._zout

    @property
    def slew(self):
        "The driver slew rate."
        return self._slew

    @property
    def zin(self):
        "The input impedance."
        return self._zin

    @property
    def ccomp(self):
        "The parasitic capacitance."
        return self._ccomp

    @property
    def mtype(self):
        """Model type."""
        return self._mtype
