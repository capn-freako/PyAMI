"""Classes for encapsulating IBIS model constituents.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   November 1, 2019

For information regarding the IBIS modeling standard, visit:
https://ibis.org/

Copyright (c) 2019 by David Banas; All rights reserved World wide.
"""

import platform
from typing import NamedTuple, Optional

from traits.api import Any, Float, HasTraits, Property, String, Trait, cached_property

from .iv import IVData

NO_CLAMP_Z = 2e6  # Impedance assumed for a missing clamp (Ohms).

# Signal direction of each ``Model_type``, per IBIS 8.0 Table 47 (lower-cased).
# ``I/O`` types are both; ``Terminator``, ``Series`` and ``Series_switch`` are neither.
_IO_MODEL_TYPES = {"i/o", "i/o_open_drain", "i/o_open_sink", "i/o_open_source", "i/o_ecl", "i/o_diff"}
TX_MODEL_TYPES = {
    "output", "3-state", "open_drain", "open_sink", "open_source",
    "output_ecl", "3-state_ecl", "output_diff", "3-state_diff",
} | _IO_MODEL_TYPES
RX_MODEL_TYPES = {"input", "input_ecl", "input_diff"} | _IO_MODEL_TYPES


class AmiExecutable(NamedTuple):
    "One ``Executable`` line of an ``[Algorithmic Model]``."

    direction: Optional[str]  # "tx" (``Executable_Tx``), "rx" (``Executable_Rx``), or ``None`` (``Executable``).
    os: str  # "linux" or "windows".
    bits: str  # "32" or "64".
    dll: str  # Executable model file name, as written in the IBIS file.
    ami: str  # AMI parameter file name, as written in the IBIS file.


class Component(HasTraits):
    """Encapsulation of a particular component from an IBIS model file."""

    # Created dynamically in ``__init__`` via ``add_trait``; declared here for static checkers.
    # ``_pin`` is the selected pin name; ``_pin_`` is the Traits mapped shadow, ``_pins[_pin]``.
    _pin: str
    _pin_: tuple[str, dict[str, float]]

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
        """The data for the pin selected most recently by the user.

        Returns the ``(model_name, rlc_dict)`` entry from the ``[Pin]`` table,
        not the pin name. (The name is in ``_pin``.) Defaults to the first
        pin's entry if the user hasn't made a selection yet.
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
            self._iv_data = IVData.from_model_dict(subDict, self._vrange[0], required=("pulldown", "pullup"))
            curves = self._iv_data.curves
            self._zout = (curves["pulldown"].impedance(self._vmeas) + curves["pullup"].impedance(self._vmeas)) / 2

            if not self._ramp:
                raise LookupError("Missing [Ramp]!")
            ramp = subDict["ramp"]
            self._slew = (ramp["rising"][0] + ramp["falling"][0]) / 2e9  # (V/ns)
        elif mtype == "input":
            self._iv_data = IVData.from_model_dict(subDict, self._vrange[0], required=("gnd_clamp", "power_clamp"))
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
        def is64(x: AmiExecutable) -> bool:
            return int(x.bits) == 64

        def isWin(x: AmiExecutable) -> bool:
            return x.os.lower() == "windows"

        def partition(p, xs):
            ts, fs = [], []
            for x in xs:
                if p(x):
                    ts.append(x)
                else:
                    fs.append(x)
            return ts, fs

        def getFiles(x: list[AmiExecutable]) -> list[str]:
            return [x[0].dll, x[0].ami] if x else []

        def splitExecs(fs):
            wins, lins = partition(isWin, fs)
            return (getFiles(wins), getFiles(lins))

        self._exec32Wins, self._exec32Lins = [], []
        self._exec64Wins, self._exec64Lins = [], []
        self._test_configs = {}
        self._ami_executables = []
        if "algorithmic_model" in subDict:
            algo_model_data = subDict["algorithmic_model"]
            self._test_configs = algo_model_data.get("test_configs", {})
            execs = [AmiExecutable(direction, os, bits, dll, ami)
                     for (direction, ((os, bits), [dll, ami])) in algo_model_data.get("executables", [])]
            self._ami_executables = execs
            exec64s, exec32s = partition(is64, execs)
            self._exec32Wins, self._exec32Lins = splitExecs(exec32s)
            self._exec64Wins, self._exec64Lins = splitExecs(exec64s)

        # Expose as traits, for viewing.
        self.add_trait("model_type", String(self._mtype))
        raw_values = {  # Numbers, typ/min/max lists, or `None` when absent.
            "c_comp": self._ccomp, "cref": self._cref, "vref": self._vref, "vmeas": self._vmeas,
            "rref": self._rref, "trange": self._trange, "vrange": self._vrange,
        }
        for name in raw_values:
            self.add_trait(name, Any())  # Values set below, not as (instance-shared) defaults.
        self.trait_set(**raw_values)
        if mtype in ("output", "i/o"):
            self.add_trait("zout", Float(self._zout))
            self.add_trait("slew", Float(self._slew))
        elif mtype == "input":
            self.add_trait("zin", Float(self._zin))

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
            res += "Algorithmic Model:\n"
            keywords = {"tx": "Executable_Tx", "rx": "Executable_Rx", None: "Executable"}
            for ex in self._ami_executables:
                res += f"\t{keywords[ex.direction]:<14}{ex.os} {ex.bits}-bit: {ex.dll}, {ex.ami}\n"
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
    def is_io(self) -> bool:
        "``I/O`` model type flag (both Tx and Rx; IBIS 8.0 Table 47)."
        return self._mtype.lower() in _IO_MODEL_TYPES

    def _platform_executables(self) -> list[AmiExecutable]:
        "The ``Executable`` entries for the running platform, in file order."
        bits = "64" if platform.architecture()[0] == "64bit" else "32"  # The interpreter's; the executable must match.
        os = "windows" if platform.system().lower() == "windows" else "linux"
        return [ex for ex in self._ami_executables if ex.os.lower() == os and ex.bits == bits]

    def get_ami_files(self, is_tx: Optional[bool] = None) -> tuple[str, str]:
        """The ``(dll, ami)`` files for the running platform and the given direction.

        Args:
            is_tx: ``True`` for Tx, ``False`` for Rx, ``None`` to follow the ``Model_type``.

        Returns:
            The files of the first matching ``Executable`` entry, or ``("", "")`` if none matches.

        Raises:
            ValueError: ``is_tx`` is ``None`` for an ``I/O`` model that has both
                ``Executable_Tx`` and ``Executable_Rx`` for this platform.

        Notes:
            1. ``I/O`` types name their files per direction (``Executable_Tx``/``Executable_Rx``) and the
            application picks the direction (IBIS 8.0 Section 10.1, p.214). A plain ``Executable``
            (illegal for them) is accepted for either direction.
            2. Other types use ``Executable``, whose direction follows the ``Model_type``. Asking for
            the other direction (or for any direction, for ``Terminator`` etc.) gives ``("", "")``.
        """
        execs = self._platform_executables()
        if self.is_io:
            if is_tx is None:
                if {"tx", "rx"} <= {ex.direction for ex in execs}:
                    raise ValueError(
                        f"I/O model has both Executable_Tx and Executable_Rx for this platform; "
                        f"use get_ami_files(is_tx) to choose one: {execs}")
            else:
                wanted = "tx" if is_tx else "rx"
                execs = [ex for ex in execs if ex.direction in (wanted, None)]
        elif is_tx is not None and self._mtype.lower() not in (TX_MODEL_TYPES if is_tx else RX_MODEL_TYPES):
            return ("", "")
        return (execs[0].dll, execs[0].ami) if execs else ("", "")

    @property
    def dll_file(self) -> str:
        """The executable model file of the first ``Executable`` entry for the running platform; empty if none.

        Direction-blind; for an ``I/O`` model with both directions, use ``get_ami_files(is_tx)``.
        """
        execs = self._platform_executables()
        return execs[0].dll if execs else ""

    @property
    def ami_file(self) -> str:
        """The AMI parameter file of the first ``Executable`` entry for the running platform; empty if none.

        Direction-blind; for an ``I/O`` model with both directions, use ``get_ami_files(is_tx)``.
        """
        execs = self._platform_executables()
        return execs[0].ami if execs else ""

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
    def ami_executables(self) -> list[AmiExecutable]:
        "The ``Executable`` entries of the ``[Algorithmic Model]``, in file order, with their direction."
        return self._ami_executables

    @property
    def executables(self) -> list:
        "Ordered ``((os, bits), [dll, ami])`` Executable entries from [Algorithmic Model], for executable_index lookup."
        return [((ex.os, ex.bits), [ex.dll, ex.ami]) for ex in self._ami_executables]
