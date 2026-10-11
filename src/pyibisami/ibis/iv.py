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
from dataclasses import dataclass, replace
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
    """One IBIS I-V table, with voltages/currents as written in the file."""

    keyword: IVKeyword
    v: NDArray[np.float64]
    i_typ: NDArray[np.float64]
    i_min: NDArray[np.float64]
    i_max: NDArray[np.float64]

    @classmethod
    def from_table(cls, keyword: IVKeyword, rows: Sequence[tuple[float, Sequence[float]]]) -> IVCurve:
        """
        Build from parsed I-V table rows.

        Args:
            keyword: The IBIS keyword the table was found under.
            rows: ``(voltage, [i_typ, i_min, i_max])`` rows.
                Missing (i.e. - "NA") min/max currents default to the typical value.

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
        i_typ = np.array([cs[0] for cs in currents], dtype=float)
        i_min = np.array([cs[1] if len(cs) > 1 else cs[0] for cs in currents], dtype=float)
        i_max = np.array([cs[2] if len(cs) > 2 else cs[0] for cs in currents], dtype=float)
        return cls(keyword, v, i_typ, i_min, i_max)

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
        """
        vs, ivals = self.v, self.current(corner)
        vthresh = vmeas if vmeas else max(vs) / 2
        # ToDo: Guard ``ix == 0`` (first table voltage already >= ``vthresh``);
        #       ``ix - 1`` currently wraps around to the last table row.
        ix = int(np.where(vs >= vthresh)[0][0])
        di = ivals[ix] - ivals[ix - 1]
        if di == 0:
            return OPEN_CIRCUIT_Z
        return float(abs((vs[ix] - vs[ix - 1]) / di))

    def ground_referenced(self, vdd: float) -> IVCurve:
        """
        Re-reference a power-rail-relative curve to ground, flipping current sense.

        Args:
            vdd: Power rail voltage.

        Returns:
            A copy, plotted on the same axes as the ground-referenced curves;
            ``self`` for curves that are already ground-referenced.
        """
        if not self.vdd_relative:
            return self
        return replace(self, v=vdd - self.v, i_typ=-self.i_typ, i_min=-self.i_min, i_max=-self.i_max)


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
    """All I-V curves of one IBIS ``[Model]``."""

    curves: Mapping[IVKeyword, IVCurve]
    vdd: float

    @classmethod
    def from_model_dict(
        cls, sub_dict: Mapping[str, object], vdd: float, required: Sequence[IVKeyword] = IV_KEYWORDS
    ) -> IVData:
        """
        Collect every I-V table found in a parsed ``[Model]`` dictionary.

        Args:
            sub_dict: Parsed ``[Model]`` sub-keywords.
            vdd: Typical power rail voltage (i.e. - ``[Voltage Range]`` typ).
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
        return cls(curves, vdd)

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
        Ground-referenced traces, ready to draw on common axes.

        Drivers show their pull-down/up curves; inputs, their clamp curves.
        Labels are ``PD-Typ``, ``PU-Max``, etc.
        """
        plotted: tuple[IVKeyword, IVKeyword] = ("pulldown", "pullup") if self.is_driver else ("gnd_clamp", "power_clamp")
        rslt = []
        for curve in (self.curves[kw] for kw in plotted if kw in self.curves):
            gnd_ref = curve.ground_referenced(self.vdd)
            prefix = "PU" if curve.side == "up" else "PD"
            for corner in ("typ", "min", "max"):
                rslt.append(IVSeries(
                    label=f"{prefix}-{corner.capitalize()}",
                    v=gnd_ref.v,
                    i=gnd_ref.current(corner),  # type: ignore[arg-type]
                    side=curve.side,
                    corner=corner,  # type: ignore[arg-type]
                ))
        return rslt
