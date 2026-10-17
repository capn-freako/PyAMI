"""Classes for encapsulating IBIS model constituents.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   November 1, 2019

For information regarding the IBIS modeling standard, visit:
https://ibis.org/

Copyright (c) 2019 by David Banas; All rights reserved World wide.
"""

import logging
import platform
from collections.abc import Mapping
from typing import NamedTuple, Optional

from traits.api import Any, Float, HasTraits, Property, String, Trait, cached_property

from .iv import IVCurve, IVData, IVKeyword

logger = logging.getLogger(__name__)

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
    os: str  # "linux", "windows", or another OS field, lower-cased (e.g. "solaris5.10"; kept, never selected).
    bits: str  # "32" or "64".
    dll: str  # Executable model file name, as written in the IBIS file.
    ami: str  # AMI parameter file name, as written in the IBIS file.


# Which analog characteristics each ``Model_type`` has, per IBIS 8.0 Section 6.1, Table 1 (lower-cased).
# ``*_ECL`` (Vcc-relative I-V tables; not supported yet) and ``*_diff`` types are deliberately absent: no zout/zin/slew.
_PUSH_PULL_TYPES = {"output", "3-state", "i/o"}
_PULLDOWN_ONLY_TYPES = {"open_drain", "open_sink", "i/o_open_drain", "i/o_open_sink"}  # Pull-up is external.
_PULLUP_ONLY_TYPES = {"open_source", "i/o_open_source"}  # Pull-down is external.
_RECEIVER_TYPES = {"input", "i/o", "i/o_open_drain", "i/o_open_sink", "i/o_open_source"}
_STRICT_DRIVER_TYPES = {"output", "i/o"}  # Missing I-V tables or [Ramp] fail the model, as they always have.
_KEYWORD_NAMES = {"pulldown": "[Pulldown]", "pullup": "[Pullup]", "ramp": "[Ramp]"}

# Spec-rule checks reported by ``Model.spec_warnings``.
_NO_ALGO_MODEL_TYPES = {"terminator", "series", "series_switch"}  # IBIS 8.0 Section 10.1, p.213.
_VINL_VINH_TYPES = {  # IBIS 8.0 Section 6.1, Table 1, p.62.
    "input", "i/o", "i/o_open_drain", "i/o_open_sink", "i/o_open_source", "input_ecl", "i/o_ecl",
}


def _clamp_impedance(curves: Mapping[IVKeyword, IVCurve], vmeas: Optional[float]) -> float:
    """Input impedance of the clamps (in parallel, as both are always active).

    ``NO_CLAMP_Z`` for a missing clamp, or one whose table doesn't reach ``vmeas``: clamp tables often cover only the
    region where the clamp conducts (e.g. - a ``[POWER Clamp]`` from -Vcc to 0 V), so it's off there.
    """
    def clamp_z(kw: IVKeyword) -> float:
        try:
            return curves[kw].impedance(vmeas) if kw in curves else NO_CLAMP_Z
        except ValueError:
            return NO_CLAMP_Z

    gc_z = clamp_z("gnd_clamp")
    pc_z = clamp_z("power_clamp")
    if "gnd_clamp" in curves and "power_clamp" in curves:
        return (gc_z * pc_z) / (gc_z + pc_z)
    if "gnd_clamp" in curves:
        return gc_z
    return pc_z


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

    def __init__(self, subDict, name: str = ""):  # pylint: disable=too-many-locals,too-many-statements
        """
        Args:
            subDict (dict): Dictionary of sub-keywords/params.

        Keyword Args:
            name: The ``[Model]`` name, for log messages.
                Default: "" (unnamed)

        Raises:
            LookupError: A required keyword is missing.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super().__init__()

        # Stash the sub-keywords/parameters.
        self._subDict = subDict
        self._name = name

        # Fetch available keyword/parameter definitions.
        def maybe(keyword):
            "The parsed value of ``keyword`` (lower-cased, as the parser stores it); ``None`` if absent."
            return subDict.get(keyword, None)

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
        self._iv_data: Optional[IVData] = None
        self._zout: Optional[float] = None
        self._slew: Optional[float] = None
        self._zin: Optional[float] = None
        self._infer_analog(subDict, name)

        # AMI executables.
        self._test_configs = {}
        self._ami_executables = []
        if "algorithmic_model" in subDict:
            algo_model_data = subDict["algorithmic_model"]
            self._test_configs = algo_model_data.get("test_configs", {})
            # All of them, in file order, for ``Executable_index``.
            self._ami_executables = [AmiExecutable(direction, os, bits, dll, ami)
                                     for (direction, ((os, bits), [dll, ami]))
                                     in algo_model_data.get("executables", [])]

        # Expose as traits, for viewing.
        self.add_trait("model_type", String(self._mtype))
        raw_values = {  # Numbers, typ/min/max lists, or `None` when absent.
            "c_comp": self._ccomp, "cref": self._cref, "vref": self._vref, "vmeas": self._vmeas,
            "rref": self._rref, "trange": self._trange, "vrange": self._vrange,
        }
        for trait_name in raw_values:
            self.add_trait(trait_name, Any())  # Values set below, not as (instance-shared) defaults.
        self.trait_set(**raw_values)
        for trait_name, value in (("zout", self._zout), ("slew", self._slew), ("zin", self._zin)):
            if value is not None:
                self.add_trait(trait_name, Float(value))

    def _infer_analog(self, subDict: dict, name: str) -> None:
        "Set ``_iv_data``, ``_zout``, ``_slew`` and ``_zin``, as far as the ``Model_type`` and its data allow."
        mtype = self._mtype.lower()
        sides: tuple[IVKeyword, ...] = ()
        if mtype in _PUSH_PULL_TYPES:
            sides = ("pulldown", "pullup")
        elif mtype in _PULLDOWN_ONLY_TYPES:
            sides = ("pulldown",)
        elif mtype in _PULLUP_ONLY_TYPES:
            sides = ("pullup",)
        if not sides and mtype not in _RECEIVER_TYPES:
            return
        strict = mtype in _STRICT_DRIVER_TYPES
        if strict and any(kw not in subDict for kw in sides):
            raise LookupError("Missing I-V curves!")
        if strict and not self._ramp:
            raise LookupError("Missing [Ramp]!")

        # ``Input`` and the strict drivers fail on an unusable table, as they always have; others skip it (with a warning).
        required: tuple[IVKeyword, ...] = ()
        if mtype == "input":
            required = ("gnd_clamp", "power_clamp")
        elif strict:
            required = sides
        iv_data = IVData.from_model_dict(subDict, self._vrange[0], required=required)
        curves = iv_data.curves
        self._iv_data = iv_data if curves else None
        if sides:
            missing = [_KEYWORD_NAMES[kw] for kw in sides if kw not in curves]
            if not self._ramp:
                missing.append(_KEYWORD_NAMES["ramp"])
            if missing:
                logger.warning("[Model] %s (%s) lacks usable %s; its output impedance and/or slew rate are unknown.",
                               name or "<unnamed>", self._mtype, ", ".join(missing))
            if all(kw in curves for kw in sides):
                try:
                    self._zout = sum(curves[kw].impedance(self._vmeas) for kw in sides) / len(sides)
                except ValueError as err:  # Vmeas off the table: no data there.
                    logger.warning("[Model] %s: %s Its output impedance is unknown.", name or "<unnamed>", err)
            if self._ramp:
                self._slew = (self._ramp["rising"][0] + self._ramp["falling"][0]) / 2e9  # (V/ns)
        if mtype in _RECEIVER_TYPES:
            self._zin = _clamp_impedance(curves, self._vmeas)

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
    def zout(self) -> Optional[float]:
        """The driver impedance (Ohms), from the slope of the pull-down/up I-V curves at ``Vmeas``.

        Push-pull types (``Output``, ``3-state``, ``I/O``) average both sides. ``Open_*``/``I/O_open_*``
        types have one side only (the other is external), so this is that side's impedance.

        ``None`` when the ``Model_type`` has no driver, its I-V data is missing, or it isn't supported yet
        (``*_ECL``, ``*_diff``).
        """
        return self._zout

    @property
    def slew(self) -> Optional[float]:
        """The driver slew rate (V/ns), from ``[Ramp]``.

        ``None`` when the ``Model_type`` has no driver, ``[Ramp]`` is missing, or it isn't supported yet
        (``*_ECL``, ``*_diff``).
        """
        return self._slew

    @property
    def zin(self) -> Optional[float]:
        """The receiver input impedance (Ohms), from the ``[GND Clamp]``/``[POWER Clamp]`` curves at ``Vmeas``.

        Both clamps act in parallel; a missing one counts as ``NO_CLAMP_Z``. Set for ``Input`` and the
        ``I/O`` types; ``None`` for other ``Model_type`` s, or ones not supported yet (``*_ECL``, ``*_diff``).
        """
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
    def spec_warnings(self) -> list[str]:
        """IBIS spec rules this model breaks, which don't stop it loading (diagnostics only).

        Checks ``[Algorithmic Model]`` use per ``Model_type`` (IBIS 8.0 Section 10.1, p.213-214, Table 47),
        the ``.ami`` file extension (p.214), and the ``Vinl``/``Vinh`` that receivers need (Section 6.1, Table 1).
        """
        mtype = self._mtype.lower()
        execs = self._ami_executables
        directions = {ex.direction for ex in execs}
        problems = []
        if self.is_ami and mtype in _NO_ALGO_MODEL_TYPES:
            problems.append(f"[Algorithmic Model] is not permitted for Model_type {self._mtype} "
                            "(IBIS 8.0 Section 10.1, p.213)")
        if self.is_io:
            if None in directions:
                problem = f"Executable is prohibited for Model_type {self._mtype}; use Executable_Tx/Executable_Rx"
                if not directions & {"tx", "rx"}:
                    problem += " (at least one is required)"
                problems.append(problem + " (IBIS 8.0 Section 10.1, p.214, Table 47)")
            tx_amis = {ex.ami for ex in execs if ex.direction == "tx"}
            shared = tx_amis & {ex.ami for ex in execs if ex.direction == "rx"}
            if shared:
                problems.append(f"Executable_Tx and Executable_Rx must name different .ami files; both use "
                                f"{', '.join(sorted(shared))} (IBIS 8.0 Section 10.1, p.214)")
        elif directions & {"tx", "rx"}:
            problems.append(f"Executable_Tx/Executable_Rx are not permitted for Model_type {self._mtype}; "
                            "use Executable (IBIS 8.0 Section 10.1, p.214, Table 47)")
        bad_ext = sorted({ex.ami for ex in execs if not ex.ami.lower().endswith(".ami")})
        if bad_ext:
            problems.append(f"AMI parameter files must have the extension .ami: {', '.join(bad_ext)} "
                            "(IBIS 8.0 Section 10.1, p.214)")
        if mtype in _VINL_VINH_TYPES:
            missing = [kw for kw in ("Vinl", "Vinh") if kw.lower() not in self._subDict]
            if missing:
                problems.append(f"{' and '.join(missing)} must be defined for Model_type {self._mtype}; "
                                "the spec default is Vinl = 0.8 V, Vinh = 2.0 V (IBIS 8.0 Section 6.1, Table 1, p.62); "
                                "not needed if the model is only used through [Diff Pin], whose vdiff supersedes them "
                                "(Section 5, p.55)")
        return [f"[Model] {self._name or '<unnamed>'}: {problem}." for problem in problems]

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
                    choices = ", ".join(f"{ex.direction or 'any'}: {ex.ami}" for ex in execs)
                    raise ValueError(
                        "I/O model has both Executable_Tx and Executable_Rx for this platform; "
                        f"use get_ami_files(is_tx) to choose one: {choices}")
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
    def ami_files(self) -> dict[str, dict[str, list[str]]]:
        """``[dll, ami]`` of the first ``Executable`` entry per bitness and OS; ``[]`` if none (direction-blind).

        Only OSes exactly ``"linux"``/``"windows"`` are listed (e.g. ``"solaris5.10"`` is in neither).
        """
        def first(bits: str, os: str) -> list[str]:
            ex = next((ex for ex in self._ami_executables if ex.bits == bits and ex.os == os), None)
            return [ex.dll, ex.ami] if ex else []

        return {f"{bits}-bit": {"lin": first(bits, "linux"), "win": first(bits, "windows")} for bits in ("32", "64")}

    @property
    def test_configs(self) -> dict:
        "Named [AMI Test Configuration] blocks from the IBIS file."
        return self._test_configs

    @property
    def ami_executables(self) -> list[AmiExecutable]:
        "The ``Executable`` entries of the ``[Algorithmic Model]``, in file order, with their direction."
        return self._ami_executables

    @property
    def executables(self) -> list[tuple[tuple[str, str], list[str]]]:
        "Ordered ``((os, bits), [dll, ami])`` Executable entries from [Algorithmic Model], for executable_index lookup."
        return [((ex.os, ex.bits), [ex.dll, ex.ami]) for ex in self._ami_executables]
