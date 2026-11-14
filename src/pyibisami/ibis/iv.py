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


def typ_value(value: object) -> Optional[float]:
    "The typical value of a parsed number or typ/min/max list; ``None`` if it's neither."
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


@dataclass(frozen=True)
class IVReferences:
    """The typical voltages a ``[Model]``'s (or ``[Submodel]``'s) I-V tables are referenced to (IBIS 8.0 Section 6.1).

    Every model has these, whether or not it has any I-V tables.
    Only typical values are kept, so every corner's table is referenced to them.
    TODO(IBIS 11): min/max references.
    """

    vdd: float  # The power rail.
    given: Mapping[IVKeyword, float] = field(default_factory=dict)  # The ``[... Reference]`` voltages given.

    @classmethod
    def from_model_dict(cls, sub_dict: Mapping[str, object], parent: Optional[IVReferences] = None) -> IVReferences:
        """
        The references a parsed ``[Model]`` (or ``[Submodel]``) gives.

        Args:
            sub_dict: Parsed ``[Model]`` (or ``[Submodel]``) sub-keywords.
            parent: The references of the model a ``[Submodel]`` is added to; its power rail is the parent's,
                as are any ``[... Reference]`` voltages it doesn't give itself.

        Returns:
            The references; the power rail is the parent's, else ``[Voltage Range]``, else (as IBIS allows, requiring
            the ``[... Reference]`` keywords instead) ``[Pullup Reference]``, else ``[POWER Clamp Reference]``.

        Raises:
            ValueError: If there's no power rail.
        """
        given = dict(parent.given) if parent else {}
        for kw in IV_KEYWORDS:
            ref = typ_value(sub_dict.get(f"{kw}_reference"))
            if ref is not None:
                given[kw] = ref
        vdd = parent.vdd if parent else typ_value(sub_dict.get("voltage_range"))
        if vdd is None:
            vdd = given.get("pullup", given.get("power_clamp"))
        if vdd is None:
            raise ValueError("Missing [Voltage Range] (or [Pullup Reference]/[POWER Clamp Reference])!")
        return cls(vdd, given)

    def reference(self, kw: IVKeyword) -> float:
        "The voltage ``kw``'s table is referenced to: its ``[... Reference]``; else, Vdd (pull-up/power) or 0 V."
        return self.given.get(kw, self.vdd if kw in VDD_RELATIVE else 0.0)

    def midway(self, low: IVKeyword, high: IVKeyword) -> float:
        "The voltage midway between ``low``'s and ``high``'s references (by default, Vdd / 2)."
        return (self.reference(low) + self.reference(high)) / 2


def _fill_na(v: NDArray[np.float64], i: NDArray[np.float64]) -> NDArray[np.float64]:
    """``i`` with its gaps (``nan``) interpolated linearly between its own values.

    ``v`` must be nondecreasing, with a known current at its lowest and highest voltages,
    so that every gap lies between known values.
    """
    known = ~np.isnan(i)
    return np.where(known, i, np.interp(v, v[known], i[known]))


@dataclass(frozen=True)
class IVCurve:
    """One IBIS I-V table, its rows in increasing voltage (the file may list them in either order).

    A voltage may repeat: a vertical step (e.g. - a diode clamp at its knee), which IBIS allows.
    """

    keyword: IVKeyword
    v: NDArray[np.float64]
    i_typ: NDArray[np.float64]
    i_min: NDArray[np.float64]
    i_max: NDArray[np.float64]
    # IBIS spec rules the table breaks, which didn't stop it loading (see ``Model.spec_warnings``).
    warnings: tuple[str, ...] = field(default=(), compare=False)

    @classmethod
    def from_table(cls, keyword: IVKeyword, rows: Sequence[tuple[float, Sequence[Optional[float]]]]) -> IVCurve:
        """
        Build from parsed I-V table rows.

        Args:
            keyword: The IBIS keyword the table was found under.
            rows: ``(voltage, [i_typ, i_min, i_max])`` rows, in any order; they're sorted by voltage.
                A missing (i.e. - "NA", ``None``) min/max current is that row's typical current, as for any other
                typ/min/max value (IBIS 8.0 Section 6.1, p.67 and p.80).
                The typical current may be missing in all but the first and last rows, as listed
                (IBIS 8.0 Section 6.1, p.91; one missing there is reported in ``warnings``);
                it's then interpolated linearly, in voltage, from its own column, as is a min/max current also
                missing from such a row.
                All rows are kept, including those repeating a voltage (a vertical step), in file order
                (reversed, for a table listed in decreasing voltage).

        Raises:
            ValueError: If there are fewer than two distinct voltages,
                or no row at the lowest or highest voltage has a typical current (so the gaps can't be filled).
        """
        if len(rows) < 2:
            raise ValueError(f"[{keyword}]: Insufficient number of I-V data points!")
        try:
            v = np.array([row[0] for row in rows], dtype=float)
            currents = [list(row[1]) for row in rows]
        except Exception as exc:
            raise ValueError(f"[{keyword}]: Malformed I-V table: {rows}") from exc
        if len(np.unique(v)) < 2:
            raise ValueError(f"[{keyword}]: Insufficient number of I-V data points!")

        def column(col: int) -> NDArray[np.float64]:
            return np.array([cs[col] if len(cs) > col and cs[col] is not None else np.nan for cs in currents],
                            dtype=float)

        warnings: list[str] = []
        given_typ = column(0)
        if np.isnan(given_typ[0]) or np.isnan(given_typ[-1]):
            warnings.append(f"[{keyword}]: The first and last rows of an I-V table must give a typical current, "
                            "not NA (IBIS 8.0 Section 6.1, p.91)")
        # Sort by voltage (``impedance()`` and ``np.interp()`` need it), keeping a vertical step's rows in curve order.
        listed = np.arange(len(v)) if v[0] <= v[-1] else np.arange(len(v))[::-1]
        order = listed[np.argsort(v[listed], kind="stable")]
        v, given_typ = v[order], given_typ[order]
        currents = [currents[k] for k in order]
        known = ~np.isnan(given_typ)
        if not (known[v == v[0]].any() and known[v == v[-1]].any()):
            raise ValueError(f"[{keyword}]: The lowest and highest voltages need a typical current (not NA).")
        i_typ = _fill_na(v, given_typ)

        def corner(col: int) -> NDArray[np.float64]:
            i = column(col)
            return _fill_na(v, np.where(np.isnan(i), given_typ, i))  # Known wherever the typical current is given.

        return cls(keyword, v, i_typ, corner(1), corner(2), tuple(warnings))

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

        The slope is that of the segment from the last row below ``vmeas`` to the first row at or above it
        (at the lowest voltage, the first segment), so a vertical step (a repeated voltage) never makes it 0 Ohms:
        at a step's own voltage, the segment leading up to the step is used.

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
        vthresh = vmeas if vmeas is not None else max(vs) / 2
        if not min(vs) <= vthresh <= max(vs):
            raise ValueError(f"[{self.keyword}]: {vthresh:g} V is outside the table ({min(vs):g} to {max(vs):g} V).")
        hi = int(np.searchsorted(vs, vthresh, side="left"))  # The first row at or above ``vthresh``.
        if vs[hi] == vs[0]:  # At the lowest voltage: the first segment, past any rows repeating it.
            hi = int(np.searchsorted(vs, vs[0], side="right"))
        lo = hi - 1  # The last row below ``vs[hi]``: there are at least two distinct voltages.
        di = ivals[hi] - ivals[lo]
        if di == 0:
            return OPEN_CIRCUIT_Z
        return float(abs((vs[hi] - vs[lo]) / di))

    def ground_referenced(self, ref: float) -> IVCurve:
        """
        Re-reference the curve's voltages to ground, i.e. - make them pin voltages.

        A ``[Pullup]``/``[POWER Clamp]`` table's voltages are ``ref - Vpin`` (its current sense is flipped, too);
        a ``[Pulldown]``/``[GND Clamp]`` table's, ``Vpin - ref``.

        Args:
            ref: The voltage the table is referenced to: its ``[... Reference]``, if given; else, the power rail
                (``[Voltage Range]``) for a ``[Pullup]``/``[POWER Clamp]`` and 0 V for a ``[Pulldown]``/``[GND Clamp]``.

        Returns:
            A copy, plotted on the same axes as the other ground-referenced curves, its rows still in increasing
            voltage; ``self`` for a curve that's already ground-referenced.
        """
        if self.vdd_relative:
            return replace(self, v=(ref - self.v)[::-1],
                           i_typ=-self.i_typ[::-1], i_min=-self.i_min[::-1], i_max=-self.i_max[::-1])
        if ref == 0:
            return self
        return replace(self, v=self.v + ref)


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
    refs: IVReferences
    # IBIS spec rules the tables break, which didn't stop the model loading (see ``Model.spec_warnings``):
    # the curves' own ``warnings``, and unusable tables skipped.
    warnings: tuple[str, ...] = field(default=(), compare=False)

    @classmethod
    def from_model_dict(
        cls, sub_dict: Mapping[str, object], refs: IVReferences | float, required: Sequence[IVKeyword] = IV_KEYWORDS
    ) -> IVData:
        """
        Collect every I-V table found in a parsed ``[Model]`` dictionary.

        Args:
            sub_dict: Parsed ``[Model]`` sub-keywords.
            refs: The model's references (see ``IVReferences.from_model_dict()``); or just its typical power rail
                voltage, the references then being those ``sub_dict`` gives.
            required: Keywords whose tables must be valid, if present.
                Any other invalid table is skipped, as reported in ``warnings``.

        Raises:
            ValueError: If a ``required`` table is invalid.
        """
        if not isinstance(refs, IVReferences):
            refs = IVReferences.from_model_dict(sub_dict, parent=IVReferences(float(refs)))
        curves: dict[IVKeyword, IVCurve] = {}
        warnings: list[str] = []
        for kw in IV_KEYWORDS:
            if kw not in sub_dict:
                continue
            try:
                curves[kw] = IVCurve.from_table(kw, sub_dict[kw])  # type: ignore[arg-type]
            except ValueError as err:
                if kw in required:
                    raise
                warnings.append(f"Ignoring unusable I-V table: {err}")
            else:
                warnings.extend(curves[kw].warnings)
        for warning in warnings:  # ``Model.spec_warnings`` carries them to the parser, which logs them at WARNING.
            logger.debug("%s", warning)
        return cls(curves, refs, tuple(warnings))

    @property
    def vdd(self) -> float:
        "The typical power rail voltage."
        return self.refs.vdd

    def reference(self, kw: IVKeyword) -> float:
        "The voltage ``kw``'s table is referenced to (see ``IVReferences.reference()``)."
        return self.refs.reference(kw)

    def ground_referenced(self, kw: IVKeyword) -> IVCurve:
        "``kw``'s curve, its voltages pin voltages (see ``IVCurve.ground_referenced()``)."
        return self.curves[kw].ground_referenced(self.reference(kw))

    def impedance(self, kw: IVKeyword, v_pin: float, corner: IVCorner = "typ") -> float:
        """
        Small-signal impedance of ``kw``'s curve at the (ground-referenced) pin voltage ``v_pin``.

        Table voltages are relative to their reference (``[Pullup]``/``[POWER Clamp]``: ref - Vpin;
        ``[Pulldown]``/``[GND Clamp]``: Vpin - ref), so the curve is re-referenced first.

        Raises:
            KeyError: If there's no ``kw`` curve.
            ValueError: If ``v_pin`` is outside the table.
        """
        return self.ground_referenced(kw).impedance(v_pin, corner)

    @property
    def rails(self) -> tuple[float, float]:
        "The lower and upper references of the plotted curves (pull-down/up, or clamps): the plot's voltage span."
        low: IVKeyword = "pulldown" if self.is_driver else "gnd_clamp"
        high: IVKeyword = "pullup" if self.is_driver else "power_clamp"
        return self.reference(low), self.reference(high)

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
        for kw in (kw for kw in plotted if kw in self.curves):
            curve, gnd_ref = self.curves[kw], self.ground_referenced(kw)
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
