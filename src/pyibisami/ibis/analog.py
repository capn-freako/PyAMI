"""Plain records of IBIS analog data.

Original author: David Patterson

Original date:   November 5, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = ["Pin"]


@dataclass(frozen=True)
class Pin:
    """One row of a component's ``[Pin]`` table (IBIS 8.0 p.36).

    ``r_pin``/``l_pin``/``c_pin`` are the per-pin parasitics; ``None`` where the table gives none (or ``NA``), meaning
    the ``[Package]`` default applies.
    """

    pin: str  # Pin name (e.g. "4", "A12").
    signal: str  # Signal name (e.g. "Tx_P").
    model: str  # Model (or [Model Selector]) name.
    r_pin: Optional[float] = None
    l_pin: Optional[float] = None
    c_pin: Optional[float] = None

    @property
    def key(self) -> str:
        "The ``pin(signal)`` name used for this pin in ``Component.pins`` and ``IBISModel.pin_name``."
        return f"{self.pin}({self.signal})"

    @classmethod
    def from_entry(cls, key: str, entry: tuple[str, dict[str, float]]) -> Pin:
        """A ``Pin`` from one ``Component.pins`` item: ``"pin(signal)"`` and ``(model, {"R_pin": …, …})``."""
        model, rlcs = entry
        name, _, rest = key.partition("(")
        return cls(name, rest.removesuffix(")"), model,
                   rlcs.get("R_pin"), rlcs.get("L_pin"), rlcs.get("C_pin"))
