"""GUI-agnostic containers for IBIS I-V curve data.

Original Author: David Patterson

Original Date:   October 10, 2026

For information regarding the IBIS modeling standard, visit:
https://ibis.org/

Copyright (c) 2026 by David Banas; All rights reserved World wide.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Literal, Optional

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

IVKeyword = Literal["pulldown", "pullup", "gnd_clamp", "power_clamp"]
IVCorner = Literal["typ", "min", "max"]
IVSide = Literal["down", "up"]

IV_KEYWORDS: tuple[IVKeyword, ...] = ("pulldown", "pullup", "gnd_clamp", "power_clamp")
VDD_RELATIVE: tuple[IVKeyword, ...] = ("pullup", "power_clamp")
OPEN_CIRCUIT_Z = 1e7  # Used in place of infinite impedance (Ohms).


@dataclass(frozen=True)
class IVCurve:
    """One IBIS I-V table, with voltages/currents as written in the file.

    Where a min or max current is ``NA`` (per cell; IBIS 8.0 p.88), ``i_min``/``i_max`` hold the typical value, so
    calculations still have a number, and ``na_min``/``na_max`` mark the cell; drawing leaves those rows out.
    """

    keyword: IVKeyword
    v: NDArray[np.float64]
    i_typ: NDArray[np.float64]
    i_min: NDArray[np.float64]
    i_max: NDArray[np.float64]
    na_min: NDArray[np.bool_] = field(default_factory=lambda: np.zeros(0, dtype=bool))
    na_max: NDArray[np.bool_] = field(default_factory=lambda: np.zeros(0, dtype=bool))

    @classmethod
    def from_table(cls, keyword: IVKeyword, rows: Sequence[tuple[float, Sequence[Optional[float]]]]) -> IVCurve:
        """
        Build from parsed I-V table rows.

        Args:
            keyword: The IBIS keyword the table was found under.
            rows: ``(voltage, [i_typ, i_min, i_max])`` rows; min/max may be ``None`` (``NA``) or left off.
                Missing (i.e. - "NA") min/max currents default to the typical value, marked in ``na_min``/``na_max``.

        Raises:
            ValueError: If there are fewer than two rows.
        """
        if len(rows) < 2:
            raise ValueError(f"[{keyword}]: Insufficient number of I-V data points!")
        try:
            v = np.array([row[0] for row in rows], dtype=float)
            currents = [list(row[1]) for row in rows]
        except Exception as exc:
            raise ValueError(f"[{keyword}]: Malformed I-V table: {rows}") from exc
        na_min = np.array([len(cs) < 2 or cs[1] is None for cs in currents])
        na_max = np.array([len(cs) < 3 or cs[2] is None for cs in currents])
        i_typ = np.array([cs[0] for cs in currents], dtype=float)
        i_min = np.array([cs[0] if na else cs[1] for cs, na in zip(currents, na_min)], dtype=float)
        i_max = np.array([cs[0] if na else cs[2] for cs, na in zip(currents, na_max)], dtype=float)
        return cls(keyword, v, i_typ, i_min, i_max, na_min, na_max)

    def _na(self, corner: IVCorner) -> NDArray[np.bool_]:
        "Which rows are ``NA`` for a corner (none, for typ)."
        na = {"typ": None, "min": self.na_min, "max": self.na_max}[corner]
        return np.zeros(len(self.v), dtype=bool) if na is None or not len(na) else na

    def has_corner(self, corner: IVCorner) -> bool:
        "Whether the table has data of its own for a corner (typ always does; ``NA`` columns don't)."
        return corner == "typ" or not bool(np.all(self._na(corner)))

    def at(self, corner: IVCorner, vdd: float) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        "``(pin voltage, current)`` for a corner, given its supply, leaving out the corner's ``NA`` rows."
        keep = ~self._na(corner)
        return self.pin_voltage(vdd)[keep], self.current(corner)[keep]

    @property
    def vdd_relative(self) -> bool:
        "True if the voltages are referenced to the power rail, as per the IBIS spec."
        return self.keyword in VDD_RELATIVE

    @property
    def side(self) -> IVSide:
        "Which rail this curve pulls toward: ``down`` (ground) or ``up`` (power)."
        return "up" if self.vdd_relative else "down"

    def current(self, corner: IVCorner = "typ") -> NDArray[np.float64]:
        "The current vector for the given corner."
        return {"typ": self.i_typ, "min": self.i_min, "max": self.i_max}[corner]

    def impedance(self, vmeas: Optional[float] = None, corner: IVCorner = "typ") -> float:
        """
        Small-signal impedance, from the slope of the curve at ``vmeas``.

        Args:
            vmeas: Voltage at which to measure the slope.
                Default: half the maximum table voltage.
            corner: Which current corner to use.

        Returns:
            Impedance (Ohms); ``OPEN_CIRCUIT_Z`` when the curve is flat there.

        Raises:
            ValueError: If ``vmeas`` is outside the table's voltages (the table says nothing there).
        """
        vs, ivals = self.v, self.current(corner)
        vthresh = vmeas if vmeas else max(vs) / 2
        if not min(vs) <= vthresh <= max(vs):
            raise ValueError(f"[{self.keyword}]: {vthresh:g} V is outside the table ({min(vs):g} to {max(vs):g} V).")
        ix = max(int(np.where(vs >= vthresh)[0][0]), 1)  # At the first table voltage, use the first segment.
        di = ivals[ix] - ivals[ix - 1]
        if di == 0:
            return OPEN_CIRCUIT_Z
        return float(abs((vs[ix] - vs[ix - 1]) / di))

    def pin_voltage(self, vdd: float) -> NDArray[np.float64]:
        """The table's voltages as pin voltages (relative to ground).

        ``[Pullup]``/``[POWER Clamp]`` voltages are ``Vcc - Vpin`` (IBIS 8.0 Section 6.1); give the supply of the
        corner being drawn (``[Voltage Range]`` typ, min or max), since each column is relative to its own.
        """
        return vdd - self.v if self.vdd_relative else self.v

    def ground_referenced(self, vdd: float) -> IVCurve:
        """
        Re-reference a power-rail-relative curve to ground (``pin_voltage(vdd)``), for one supply voltage.

        Currents keep their IBIS sense: positive into the pin, in every table.

        Args:
            vdd: Power rail voltage.

        Returns:
            A copy, plotted on the same axes as the ground-referenced curves;
            ``self`` for curves that are already ground-referenced.
        """
        if not self.vdd_relative:
            return self
        return replace(self, v=self.pin_voltage(vdd))


@dataclass(frozen=True)
class IVSeries:
    """One drawable trace, with toolkit-neutral style hints."""

    label: str
    v: NDArray[np.float64]
    i: NDArray[np.float64]
    side: IVSide
    corner: IVCorner


@dataclass(frozen=True)
class IVData:
    """All I-V curves of one IBIS ``[Model]``.

    ``vdd`` is the typical supply (``[Voltage Range]`` typ); ``vdd_min``/``vdd_max`` its min and max (``None``: typ).
    """

    curves: Mapping[IVKeyword, IVCurve]
    vdd: float
    vdd_min: Optional[float] = None
    vdd_max: Optional[float] = None

    @classmethod
    def from_model_dict(
        cls, sub_dict: Mapping[str, object], vdd: float | Sequence[float], required: Sequence[IVKeyword] = IV_KEYWORDS
    ) -> IVData:
        """
        Collect every I-V table found in a parsed ``[Model]`` dictionary.

        Args:
            sub_dict: Parsed ``[Model]`` sub-keywords.
            vdd: The power rail voltage: ``[Voltage Range]`` as ``[typ, min, max]`` (or ``[typ]``), or just typ.
            required: Keywords whose tables must be valid, if present.
                Any other invalid table is skipped, with a warning.

        Raises:
            ValueError: If a ``required`` table is invalid.
        """
        curves: dict[IVKeyword, IVCurve] = {}
        for kw in IV_KEYWORDS:
            if kw not in sub_dict:
                continue
            try:
                curves[kw] = IVCurve.from_table(kw, sub_dict[kw])  # type: ignore[arg-type]
            except ValueError as err:
                if kw in required:
                    raise
                logger.warning("Ignoring unusable I-V table: %s", err)
        supplies = [float(v) for v in vdd] if isinstance(vdd, Sequence) else [float(vdd)]
        return cls(curves, supplies[0], *(supplies[1:3] if len(supplies) >= 3 else (None, None)))

    def supply(self, corner: IVCorner = "typ") -> float:
        "The supply voltage of a corner: ``vdd``, ``vdd_min`` or ``vdd_max`` (typ where not given)."
        value = {"typ": self.vdd, "min": self.vdd_min, "max": self.vdd_max}[corner]
        return self.vdd if value is None else value

    @property
    def is_driver(self) -> bool:
        "True for output (pull-up/down) curves; False for input (clamp) curves."
        return "pulldown" in self.curves or "pullup" in self.curves

    @property
    def title(self) -> str:
        "Plot title."
        return "Pull-Up/Down I-V Curves" if self.is_driver else "Power/GND Clamp I-V Curves"

    @property
    def v_label(self) -> str:
        "Voltage axis label."
        return "Vout (V)" if self.is_driver else "Vin (V)"

    @property
    def i_label(self) -> str:
        "Current axis label."
        return "Iout (A)" if self.is_driver else "Iin (A)"

    def series(self) -> list[IVSeries]:
        """
        Traces against pin voltage, ready to draw on common axes.

        ``[Pullup]``/``[POWER Clamp]`` voltages (``Vcc - Vpin``) are turned into pin voltages with each corner's own
        supply (``supply(corner)``); currents keep their IBIS sense (positive into the pin).
        Drivers show their pull-down/up curves; inputs, their clamp curves.
        Labels are ``PD-Typ``, ``PU-Max``, etc. A min/max corner's ``NA`` rows are left out (the whole trace, if
        it's ``NA`` throughout).
        """
        plotted: tuple[IVKeyword, IVKeyword] = ("pulldown", "pullup") if self.is_driver else ("gnd_clamp", "power_clamp")
        rslt = []
        for curve in (self.curves[kw] for kw in plotted if kw in self.curves):
            prefix = "PU" if curve.side == "up" else "PD"
            for corner in ("typ", "min", "max"):
                if not curve.has_corner(corner):  # type: ignore[arg-type]
                    continue
                v, i = curve.at(corner, self.supply(corner))  # type: ignore[arg-type]
                rslt.append(IVSeries(
                    label=f"{prefix}-{corner.capitalize()}",
                    v=v,
                    i=i,
                    side=curve.side,
                    corner=corner,  # type: ignore[arg-type]
                ))
        return rslt
