"""GUI-agnostic containers for IBIS V-T waveform data (``[Rising Waveform]``/``[Falling Waveform]``).

Original Author: David Patterson

Original Date:   November 5, 2026

For information regarding the IBIS modeling standard, visit:
https://ibis.org/

Copyright (c) 2026 by David Banas; All rights reserved World wide.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Optional

import numpy as np
from numpy.typing import NDArray

from .iv import IVCorner

__all__ = ["MAX_VT_ROWS", "MAX_VT_TABLES", "Fixture", "VTSeries", "VTWaveform"]

VTDirection = Literal["rising", "falling"]

# IBIS 8.0 Section 6.1, p.107.
MAX_VT_ROWS = 1000
MAX_VT_TABLES = 100
_FIXTURE_PARAMS = ("r_fixture", "v_fixture", "v_fixture_min", "v_fixture_max", "c_fixture", "l_fixture",
                   "r_dut", "l_dut", "c_dut")


@dataclass(frozen=True)
class Fixture:  # pylint: disable=too-many-instance-attributes
    """The load a V-T waveform was taken into (IBIS 8.0 p.108, Figure 18).

    Only ``R_fixture`` and ``V_fixture`` are required; the others default to zero, except ``V_fixture_min``/
    ``V_fixture_max`` (``None``: ``V_fixture`` applies to every corner).
    """

    r_fixture: float
    v_fixture: float
    v_fixture_min: Optional[float] = None
    v_fixture_max: Optional[float] = None
    c_fixture: float = 0.0
    l_fixture: float = 0.0
    r_dut: float = 0.0
    l_dut: float = 0.0
    c_dut: float = 0.0

    @classmethod
    def from_params(cls, params: Mapping[str, Any]) -> Fixture:
        """From a waveform's subparameters (names lower-cased).

        Raises:
            ValueError: ``R_fixture`` or ``V_fixture`` is missing, or a value isn't a number.
        """
        missing = [name for name in ("r_fixture", "v_fixture") if name not in params]
        if missing:
            raise ValueError(f"Missing required subparameter(s): {', '.join(m.capitalize() for m in missing)}")
        try:
            return cls(**{name: float(params[name]) for name in _FIXTURE_PARAMS if name in params})
        except (TypeError, ValueError) as err:
            raise ValueError(f"Non-numeric fixture subparameter: {dict(params)}") from err

    def v(self, corner: IVCorner = "typ") -> float:
        "The fixture voltage for a corner (``V_fixture_min``/``_max`` if given, else ``V_fixture``)."
        value = {"min": self.v_fixture_min, "max": self.v_fixture_max}.get(corner)
        return self.v_fixture if value is None else value


@dataclass(frozen=True)
class VTSeries:
    "One drawable V-T trace."

    label: str
    t: NDArray[np.float64]
    v: NDArray[np.float64]
    direction: VTDirection
    corner: IVCorner


@dataclass(frozen=True)
class VTWaveform:  # pylint: disable=too-many-instance-attributes
    """One ``[Rising Waveform]`` or ``[Falling Waveform]`` table, as written in the file.

    ``v_min``/``v_max`` hold ``nan`` where the table says ``NA``; ``na_min``/``na_max`` mark those rows.
    """

    direction: VTDirection
    fixture: Fixture
    t: NDArray[np.float64]
    v_typ: NDArray[np.float64]
    v_min: NDArray[np.float64]
    v_max: NDArray[np.float64]
    na_min: NDArray[np.bool_]
    na_max: NDArray[np.bool_]

    @classmethod
    def from_table(
        cls, direction: VTDirection, params: Mapping[str, Any],
        rows: Sequence[tuple[float, float, Optional[float], Optional[float]]],
    ) -> VTWaveform:
        """
        Build from a parsed waveform keyword.

        Args:
            direction: ``rising`` or ``falling``.
            params: The fixture subparameters, by lower-cased name.
            rows: ``(time, v_typ, v_min, v_max)`` rows; ``None`` for ``NA``.

        Raises:
            ValueError: A required subparameter is missing, there are fewer than two rows, or the times
                don't increase (IBIS 8.0 p.107).
        """
        fixture = Fixture.from_params(params)
        if len(rows) < 2:
            raise ValueError(f"[{direction.capitalize()} Waveform]: needs at least two rows; got {len(rows)}.")
        t = np.array([row[0] for row in rows], dtype=float)
        if np.any(np.diff(t) <= 0):
            raise ValueError(f"[{direction.capitalize()} Waveform]: times must increase.")

        def column(ix: int) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
            values = [row[ix] for row in rows]
            na = np.array([value is None for value in values])
            return np.array([np.nan if value is None else value for value in values], dtype=float), na

        v_typ, _ = column(1)
        v_min, na_min = column(2)
        v_max, na_max = column(3)
        return cls(direction, fixture, t, v_typ, v_min, v_max, na_min, na_max)

    def voltage(self, corner: IVCorner = "typ") -> NDArray[np.float64]:
        "The voltage column for a corner (``nan`` where ``NA``)."
        return {"typ": self.v_typ, "min": self.v_min, "max": self.v_max}[corner]

    def has_corner(self, corner: IVCorner) -> bool:
        "Whether the table has any data for a corner (typ always does)."
        na = {"typ": None, "min": self.na_min, "max": self.na_max}[corner]
        return na is None or not bool(np.all(na))

    def at(self, corner: IVCorner = "typ") -> tuple[NDArray[np.float64], NDArray[np.float64], float]:
        "``(t, v, v_fixture)`` for a corner, leaving out its ``NA`` rows."
        v = self.voltage(corner)
        keep = ~np.isnan(v)
        return self.t[keep], v[keep], self.fixture.v(corner)

    @property
    def label(self) -> str:
        "A short name: direction and fixture, e.g. ``Rising, 50 Ohm to 0 V``."
        f = self.fixture
        return f"{self.direction.capitalize()}, {f.r_fixture:g} Ohm to {f.v_fixture:g} V"

    def series(self) -> list[VTSeries]:
        "One trace per corner with data, labelled e.g. ``Rising, 50 Ohm to 0 V (typ)``."
        rslt = []
        for corner in ("typ", "min", "max"):
            if self.has_corner(corner):  # type: ignore[arg-type]
                t, v, _ = self.at(corner)  # type: ignore[arg-type]
                rslt.append(VTSeries(f"{self.label} ({corner})", t, v, self.direction, corner))  # type: ignore[arg-type]
        return rslt
