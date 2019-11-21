"""
Classes for encapsulating IBIS model constituents.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   November 1, 2019

For information regarding the IBIS modeling standard, visit:
https://ibis.org/

Copyright (c) 2019 by David Banas; All rights reserved World wide.
"""

import numpy      as np

from traits.api   import HasTraits, Trait, String, Float, List
from traitsui.api import Item, View, ModalButtons, Group, spring
from chaco.api    import ArrayPlotData, Plot
from enable.component_editor import ComponentEditor

class Component(HasTraits):
    """Encapsulation of a particular component from an IBIS model file.
    """

    def __init__(self, subDict):
        """
        Args:
            subDict (dict): Dictionary of sub-keywords/params.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super(Component, self).__init__()

        # Stash the sub-keywords/parameters.
        self._subDict = subDict

        # Fetch available keyword/parameter definitions.
        def maybe(name):
            return subDict[name] if name in subDict else None
        self._mfr   = maybe('manufacturer')
        self._pkg   = maybe('package')
        self._pins  = maybe('pin')
        self._diffs = maybe('diff_pin')

        # Check for the required keywords.
        if not self._mfr:
            raise LookupError("Missing [Manufacturer]!")
        if not self._pkg:
            print(self._mfr)
            raise LookupError("Missing [Package]!")
        if not self._pins:
            raise LookupError("Missing [Pin]!")
        
        # Set up the GUI.
        self.add_trait('manufacturer', String(self._mfr))
        self.add_trait('package',      String(self._pkg))
        self.add_trait('_pin',         Trait(list(self._pins)[0], self._pins))
        self._content = [
            Group(
                Item('manufacturer', label='Manufacturer', style='readonly'),
                Item('package',      label='Package',      style='readonly'),
                Item('_pin',         label='Pin'),
                label='Component', show_border=True,
            ),
        ]

    def __str__(self):
        res  = "Manufacturer:\t" + self._mfr       + '\n'
        res += "Package:     \t" + str(self._pkg)  + '\n'
        res += "Pins:\n"
        for pname in self._pins:
            res += "    " + pname + ":\t" + str(self._pins[pname]) + '\n'
        return res

    def __call__(self):
        self.edit_traits()

    def default_traits_view(self):
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

        Returns the first pin in the list, if the user hasn't made a selection yet.
        """
        return self._pin_

    @property
    def pins(self):
        "The list of component pins."
        return self._pins

class Model(HasTraits):
    """Encapsulation of a particular I/O model from an IBIS model file.
    """

    def __init__(self, subDict):
        """
        Args:
            subDict (dict): Dictionary of sub-keywords/params.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super(Model, self).__init__()

        # Stash the sub-keywords/parameters.
        self._subDict = subDict

        # Fetch available keyword/parameter definitions.
        def maybe(name):
            return subDict[name] if name in subDict else None
        self._mtype  = maybe('model_type')
        self._ccomp  = maybe('c_comp')
        self._cref   = maybe('cref')
        self._vref   = maybe('vref')
        self._vmeas  = maybe('vmeas')
        self._rref   = maybe('rref')
        self._trange = maybe('temperature_range')
        self._vrange = maybe('voltage_range')
        self._ramp   = maybe('ramp')

        # Check for the required keywords.
        if not self._mtype:
            raise LookupError("Missing Model_type!")
        if not self._vrange:
            raise LookupError("Missing [Voltage Range]!")
        
        # Infer impedance and rise/fall time for output models.
        if self._mtype == 'Output':
            if 'pulldown' not in subDict or 'pullup' not in subDict:
                raise LookupError("Missing I-V curves!")
            plotdata = ArrayPlotData()
            def proc_iv(xs):
                if len(xs) < 2:
                    raise ValueError("Insufficient number of I-V data points!")
                vs, iss = zip(*(xs))  # Idiomatic Python for `unzip`.
                ityps, imins, imaxs = zip(*iss)
                vmeas = self._vmeas
                def calcZ(x):
                    (vs, ivals) = x
                    if vmeas:
                        ix = np.where(np.array(vs) >= vmeas)[0][0]
                    else:
                        ix = np.where(np.array(vs) >= max(vs)/2)[0][0]
                    return abs((vs[ix] - vs[ix-1])/(ivals[ix] - ivals[ix-1]))
                zs = map(calcZ, zip([vs, vs, vs], [ityps, imins, imaxs]))
                return vs, ityps, imins, imaxs, zs
            pd_vs, pd_ityps, pd_imins, pd_imaxs, pd_zs = proc_iv(subDict['pulldown'])
            pu_vs, pu_ityps, pu_imins, pu_imaxs, pu_zs = proc_iv(subDict['pullup'])
            pu_vs = self._vrange[0] - np.array(pu_vs)  # Correct for Vdd-relative pull-up voltages.
            pu_ityps = -np.array(pu_ityps)             # Correct for current sense, for nicer plot.
            pu_imins = -np.array(pu_imins)
            pu_imaxs = -np.array(pu_imaxs)
            self._zout = (list(pd_zs)[0] + list(pu_zs)[0])/2
            plotdata.set_data("pd_vs",    pd_vs)
            plotdata.set_data("pd_ityps", pd_ityps)
            plotdata.set_data("pd_imins", pd_imins)
            plotdata.set_data("pd_imaxs", pd_imaxs)
            plotdata.set_data("pu_vs",    pu_vs)
            plotdata.set_data("pu_ityps", pu_ityps)
            plotdata.set_data("pu_imins", pu_imins)
            plotdata.set_data("pu_imaxs", pu_imaxs)
            plot_iv = Plot(plotdata)  # , padding_left=75)
            # The 'line_style' trait of a LinePlot instance must be 'dash' or 'dot dash' or 'dot' or 'long dash' or 'solid'.
            plot_iv.plot(("pd_vs", "pd_ityps"), type="line", color="blue", line_style="solid", name="PD-Typ")
            plot_iv.plot(("pd_vs", "pd_imins"), type="line", color="blue", line_style="dot",   name="PD-Min")
            plot_iv.plot(("pd_vs", "pd_imaxs"), type="line", color="blue", line_style="dash",  name="PD-Max")
            plot_iv.plot(("pu_vs", "pu_ityps"), type="line", color="red",  line_style="solid", name="PU-Typ")
            plot_iv.plot(("pu_vs", "pu_imins"), type="line", color="red",  line_style="dot",   name="PU-Min")
            plot_iv.plot(("pu_vs", "pu_imaxs"), type="line", color="red",  line_style="dash",  name="PU-Max")
            plot_iv.title = "Pull-Up/Down I-V Curves"
            plot_iv.index_axis.title = "Vout (V)"
            plot_iv.value_axis.title = "Iout (A)"
            plot_iv.index_range.low_setting  = 0
            plot_iv.index_range.high_setting = self._vrange[0]
            plot_iv.value_range.low_setting  = 0
            plot_iv.value_range.high_setting = 0.1
            plot_iv.legend.visible = True
            plot_iv.legend.align = "ul"
            self.plot_iv = plot_iv

            if not self._ramp:
                raise LookupError("Missing [Ramp]!")
            ramp = subDict['ramp']
            self._slew = (ramp['rising'][0] + ramp['falling'][0])/2e9  # (V/ns)

        # Separate AMI executables by OS.
        def is64(x):
            ((_, b), _) = x
            return int(b) == 64

        def isWin(x):
            ((os, _), _) = x
            return os == 'Windows'

        def showExec(x):
            ((os, b), fs) = x
            return os + str(b) + ': ' + str(fs)

        def partition(p, xs):
            ts, fs = [], []
            for x in xs:
                ts.append(x) if p(x) else fs.append(x)
            return ts, fs

        def getFiles(x):
            ((_, _), fs) = x
            return fs

        if 'algorithmic_model' in subDict:
            execs = subDict['algorithmic_model']
            exec64s, exec32s = partition(is64, execs)
            self._exec32Wins, self._exec32Lins = list(map(lambda x: list(map(getFiles, x))[0], partition(isWin, exec32s)))
            self._exec64Wins, self._exec64Lins = list(map(lambda x: list(map(getFiles, x))[0], partition(isWin, exec64s)))
        else:
            self._exec32Wins, self._exec32Lins = [], []
            self._exec64Wins, self._exec64Lins = [], []

        # Set up the GUI.
        self.add_trait('model_type', String(self._mtype))
        self.add_trait('c_comp', String(self._ccomp))
        self.add_trait('cref',   String(self._cref))
        self.add_trait('vref',   String(self._vref))
        self.add_trait('vmeas',  String(self._vmeas))
        self.add_trait('rref',   String(self._rref))
        self.add_trait('trange', String(self._trange))
        self.add_trait('vrange', String(self._vrange))
        if self._mtype == 'Output':
            self.add_trait('zout',   String(self._zout))
            self.add_trait('slew',   String(self._slew))
        self._content = [
            Group(
                Item('model_type', label='Model type',            style='readonly'),
                Item('c_comp',     label='Ccomp',                 style='readonly'),
                Item('trange',     label='Temperature Range',     style='readonly'),
                Item('vrange',     label='Voltage Range',         style='readonly'),
                Group(
                    Item('cref', label='Cref', style='readonly'),
                    Item('vref', label='Vref', style='readonly'),
                    Item('vmeas', label='Vmeas', style='readonly'),
                    Item('rref', label='Rref', style='readonly'),
                    orientation="horizontal",
                ),
                label='Model', show_border=True,
            ),
        ]
        if self._mtype == 'Output':
            self._content.append(Item('zout',       label='Impedance (Ohms)',      style='readonly', format_str='%4.1f'))
            self._content.append(Item('slew',       label='Slew Rate (V/ns)',      style='readonly', format_str='%4.1f'))
            self._content.append(Item('plot_iv', editor=ComponentEditor(), show_label=False))

    def __str__(self):
        res = "Model Type:\t" + self._mtype + '\n'
        res += "C_comp:    \t" + str(self._ccomp) + '\n'
        res += "Cref:      \t" + str(self._cref)  + '\n'
        res += "Vref:      \t" + str(self._vref)  + '\n'
        res += "Vmeas:     \t" + str(self._vmeas) + '\n'
        res += "Rref:      \t" + str(self._rref)  + '\n'
        res += "Temperature Range:\t" + str(self._trange) + '\n'
        res += "Voltage Range:    \t" + str(self._vrange) + '\n'
        if 'algorithmic_model' in self._subDict:
            res += "Algorithmic Model:\n" \
                   + "\t32-bit:\n"
            if self._exec32Lins:
                res += "\t\tLinux: "   + str(self._exec32Lins) + '\n'
            if self._exec32Wins:
                res += "\t\tWindows: " + str(self._exec32Wins) + '\n'
            res += "\t64-bit:\n"
            if self._exec64Lins:
                res += "\t\tLinux: "   + str(self._exec64Lins) + '\n'
            if self._exec64Wins:
                res += "\t\tWindows: " + str(self._exec64Wins) + '\n'
        return res

    def __call__(self):
        self.edit_traits()

    def default_traits_view(self):
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
        "The driver impedance."
        return self._slew
        
    @property
    def ccomp(self):
        "The driver impedance."
        return self._ccomp
        
