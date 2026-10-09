"""Classes for encapsulating IBIS model constituents.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   November 1, 2019

For information regarding the IBIS modeling standard, visit:
https://ibis.org/

Copyright (c) 2019 by David Banas; All rights reserved World wide.

**Note:** These classes hold no GUI machinery, so that IBIS parsing doesn't require
the (optional) GUI dependencies. Their viewers live in ``pyibisami.ibis.gui``.
"""

import numpy as np

IVCurve = dict[str, np.ndarray]  # Keys: "vs", "ityps", "imins", "imaxs".


class Component:
    """Encapsulation of a particular component from an IBIS model file."""

    def __init__(self, subDict):
        """
        Args:
            subDict(dict): Dictionary of [Component] sub-keywords/params.
        """

        # Stash the sub-keywords/parameters.
        self._subDict = subDict

        # Fetch available keyword/parameter definitions,
        # flagging an error if any required keywords are missing.
        self._mfr = subDict["manufacturer"]    # Will flag error if missing.
        self._pkg = subDict["package"]
        self._pins = subDict["pin"]
        self._diffs = subDict.get("diff_pin")  # Won't flag error; returns `None`.
        self._pin_name = next(iter(self._pins))  # Updated by the GUI viewer.

    def __str__(self):
        res = "Manufacturer:\t" + self._mfr + "\n"
        res += "Package:     \t" + str(self._pkg) + "\n"
        res += "Pins:\n"
        for pname in self._pins:
            res += "    " + pname + ":\t" + str(self._pins[pname]) + "\n"
        return res

    def __call__(self):
        """Present a GUI viewer. (Requires the optional GUI dependencies.)"""
        from .gui import ComponentView  # pylint: disable=import-outside-toplevel
        ComponentView(self).edit_traits()

    @property
    def manufacturer(self):
        "The component manufacturer."
        return self._mfr

    @property
    def package(self):
        "The component package parasitics."
        return self._pkg

    @property
    def pin(self):
        """The pin selected most recently by the user.

        Returns the first pin in the list, if the user hasn't made a
        selection yet.
        """
        return self._pins[self._pin_name]

    @property
    def pins(self):
        "The list of component pins."
        return self._pins


class Model:  # pylint: disable=too-many-instance-attributes
    """Encapsulation of a particular I/O model from an IBIS model file."""

    def __init__(self, subDict):  # pylint: disable=too-many-locals,too-many-statements,too-many-branches
        """
        Args:
            subDict (dict): Dictionary of sub-keywords/params.
        """

        # Stash the sub-keywords/parameters.
        self._subDict = subDict
        self._iv_curves: dict[str, IVCurve] = {}

        # Fetch available keyword/parameter definitions.
        def maybe(name):
            return subDict.get(name, None)

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

        def iv_curve(vs, ityps, imins, imaxs) -> IVCurve:
            return {"vs": np.array(vs), "ityps": np.array(ityps), "imins": np.array(imins), "imaxs": np.array(imaxs)}

        # Infer impedance and/or rise/fall time, as per model type.
        mtype = self._mtype.lower()
        if mtype in ("output", "i/o"):
            if "pulldown" not in subDict or "pullup" not in subDict:
                raise LookupError("Missing I-V curves!")
            pd_vs, pd_ityps, pd_imins, pd_imaxs, pd_zs = proc_iv(subDict["pulldown"])
            pu_vs, pu_ityps, pu_imins, pu_imaxs, pu_zs = proc_iv(subDict["pullup"])
            pu_vs = self._vrange[0] - np.array(pu_vs)  # Correct for Vdd-relative pull-up voltages.
            pu_ityps = -np.array(pu_ityps)  # Correct for current sense, for nicer plot.
            pu_imins = -np.array(pu_imins)
            pu_imaxs = -np.array(pu_imaxs)
            self._zout = (next(iter(pd_zs)) + next(iter(pu_zs))) / 2
            self._iv_curves["pulldown"] = iv_curve(pd_vs, pd_ityps, pd_imins, pd_imaxs)
            self._iv_curves["pullup"] = iv_curve(pu_vs, pu_ityps, pu_imins, pu_imaxs)

            if not self._ramp:
                raise LookupError("Missing [Ramp]!")
            ramp = subDict["ramp"]
            self._slew = (ramp["rising"][0] + ramp["falling"][0]) / 2e9  # (V/ns)
        elif mtype == "input":
            if "gnd_clamp" not in subDict and "power_clamp" not in subDict:
                pass

            if "gnd_clamp" in subDict:
                gc_vs, gc_ityps, gc_imins, gc_imaxs, gc_zs = proc_iv(subDict["gnd_clamp"])
                gc_z = next(iter(gc_zs))  # Use typical value for Zin calc.
                self._iv_curves["gnd_clamp"] = iv_curve(gc_vs, gc_ityps, gc_imins, gc_imaxs)
            else:
                gc_z = 2e6

            if "power_clamp" in subDict:
                pc_vs, pc_ityps, pc_imins, pc_imaxs, pc_zs = proc_iv(subDict["power_clamp"])
                pc_z = next(iter(pc_zs))
                pc_vs = self._vrange[0] - np.array(pc_vs)  # Correct for Vdd-relative pull-up voltages.
                pc_ityps = -np.array(pc_ityps)  # Correct for current sense, for nicer plot.
                pc_imins = -np.array(pc_imins)
                pc_imaxs = -np.array(pc_imaxs)
                self._iv_curves["power_clamp"] = iv_curve(pc_vs, pc_ityps, pc_imins, pc_imaxs)
            else:
                pc_z = 2e6

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
        self._test_configs = {}
        self._executables = []
        if "algorithmic_model" in subDict:
            algo_model_data = subDict["algorithmic_model"]
            execs = algo_model_data.get("executables", [])
            self._test_configs = algo_model_data.get("test_configs", {})
            self._executables = execs
            exec64s, exec32s = partition(is64, execs)
            self._exec32Wins, self._exec32Lins = splitExecs(exec32s)
            self._exec64Wins, self._exec64Lins = splitExecs(exec64s)

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
        """Present a GUI viewer. (Requires the optional GUI dependencies.)"""
        from .gui import ModelView  # pylint: disable=import-outside-toplevel
        ModelView(self).edit_traits(kind="livemodal")

    @property
    def iv_curves(self) -> dict[str, IVCurve]:
        """The processed I-V curves, keyed by IBIS keyword:

        "pulldown"/"pullup" (Output, I/O) or "gnd_clamp"/"power_clamp" (Input, if present).
        Each holds "vs", "ityps", "imins", and "imaxs" arrays, with pull-up/power-clamp
        voltages made ground-relative and their currents negated.
        """
        return self._iv_curves

    @property
    def plot_iv(self):
        """A Chaco plot of the I-V curves. (Requires the optional GUI dependencies.)"""
        from .gui import make_iv_plot  # pylint: disable=import-outside-toplevel
        return make_iv_plot(self)

    @property
    def trange(self):
        "Temperature range."
        return self._trange

    @property
    def vrange(self):
        "Voltage range."
        return self._vrange

    @property
    def cref(self):
        "Timing test load capacitance."
        return self._cref

    @property
    def vref(self):
        "Timing test load voltage."
        return self._vref

    @property
    def vmeas(self):
        "Timing measurement voltage."
        return self._vmeas

    @property
    def rref(self):
        "Timing test load resistance."
        return self._rref

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
        "Model type."
        return self._mtype

    @property
    def is_ami(self):
        "AMI model flag."
        return ("algorithmic_model" in self._subDict)

    @property
    def ami_files(self):
        return {
            "32-bit": {"lin": self._exec32Lins, "win": self._exec32Wins},
            "64-bit": {"lin": self._exec64Lins, "win": self._exec64Wins}
        }

    @property
    def test_configs(self) -> dict:
        "Named [AMI Test Configuration] blocks from the IBIS file."
        return self._test_configs

    @property
    def executables(self) -> list:
        "Raw ordered list of Executable entries from [Algorithmic Model], for executable_index lookup."
        return self._executables
