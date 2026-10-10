"""Classes for encapsulating IBIS model constituents.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   November 1, 2019

For information regarding the IBIS modeling standard, visit:
https://ibis.org/

Copyright (c) 2019 by David Banas; All rights reserved World wide.
"""

from typing import Optional

from traits.api import Any, HasTraits, Property, String, Trait, cached_property

from .iv import IVData

NO_CLAMP_Z = 2e6  # Impedance assumed for a missing clamp (Ohms).


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

        # Fetch available keyword/parameter definitions,
        # flagging an error if any required keywords are missing.
        self._mfr = subDict["manufacturer"]    # Will flag error if missing.
        self._pkg = subDict["package"]
        self._pins = subDict["pin"]
        self._diffs = subDict.get("diff_pin")  # Won't flag error; returns `None`.

        # Expose as traits, for viewing/selection.
        self.add_trait("manufacturer", String(self._mfr))
        self.add_trait("package", String(self._pkg))
        self.add_trait("_pin", Trait(next(iter(self._pins)), self._pins))

    def __str__(self):
        res = "Manufacturer:\t" + self._mfr + "\n"
        res += "Package:     \t" + str(self._pkg) + "\n"
        res += "Pins:\n"
        for pname in self._pins:
            res += "    " + pname + ":\t" + str(self._pins[pname]) + "\n"
        return res

    def __call__(self):
        """Present the component viewer GUI.

        Requires the ``gui`` extra: ``pip install 'pyibis-ami[gui]'``.
        """
        from .. import gui  # noqa: F401  # pylint: disable=import-outside-toplevel,unused-import
        self.edit_traits()

    def default_traits_view(self):
        "Default Traits/UI view definition."
        from ..gui.ibis import make_component_view  # pylint: disable=import-outside-toplevel
        return make_component_view(self)

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

    # Chaco plot of ``iv_data``, built on first access; requires the ``gui`` extra.
    plot_iv = Property(Any)

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

        # Infer impedance and/or rise/fall time, as per model type.
        self._iv_data = None
        mtype = self._mtype.lower()
        if mtype in ("output", "i/o"):
            if "pulldown" not in subDict or "pullup" not in subDict:
                raise LookupError("Missing I-V curves!")
            self._iv_data = IVData.from_model_dict(subDict, self._vrange[0])
            curves = self._iv_data.curves
            self._zout = (curves["pulldown"].impedance(self._vmeas) + curves["pullup"].impedance(self._vmeas)) / 2

            if not self._ramp:
                raise LookupError("Missing [Ramp]!")
            ramp = subDict["ramp"]
            self._slew = (ramp["rising"][0] + ramp["falling"][0]) / 2e9  # (V/ns)
        elif mtype == "input":
            self._iv_data = IVData.from_model_dict(subDict, self._vrange[0])
            curves = self._iv_data.curves
            gc_z = curves["gnd_clamp"].impedance(self._vmeas) if "gnd_clamp" in curves else NO_CLAMP_Z
            pc_z = curves["power_clamp"].impedance(self._vmeas) if "power_clamp" in curves else NO_CLAMP_Z
            if "gnd_clamp" in curves and "power_clamp" in curves:
                # Parallel combination, as both clamps are always active.
                self._zin = (gc_z * pc_z) / (gc_z + pc_z)
            elif "gnd_clamp" in curves:
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

        # Expose as traits, for viewing.
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
        """Present the model viewer GUI.

        Requires the ``gui`` extra: ``pip install 'pyibis-ami[gui]'``.
        """
        from .. import gui  # noqa: F401  # pylint: disable=import-outside-toplevel,unused-import
        self.edit_traits(kind="livemodal")

    def default_traits_view(self):
        "Default Traits/UI view definition."
        from ..gui.ibis import make_model_view  # pylint: disable=import-outside-toplevel
        return make_model_view(self)

    @cached_property
    def _get_plot_iv(self):
        if self._iv_data is None:
            return None
        from ..gui.ibis import make_iv_plot  # pylint: disable=import-outside-toplevel
        return make_iv_plot(self._iv_data)

    @property
    def iv_data(self) -> Optional[IVData]:
        "The I-V curves of this model; ``None`` for model types without any."
        return self._iv_data

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
