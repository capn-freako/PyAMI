"""I-V and V-T plot widgets (matplotlib, Qt backend).

One table kind per widget: ``IVPlot`` shows one side (pulldown/GND clamp or pullup/POWER clamp) and ``VTPlot`` one
direction (rising or falling), so each can have its own tab.

Hovering shows the cursor's (x, y) in the toolbar (matplotlib's own readout).

Original Author: David Patterson

Original Date:   November 5, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Optional

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QVBoxLayout, QWidget

from ..ibis.iv import IVData, IVSide
from ..ibis.vt import VTDirection, VTWaveform

__all__ = ["IVPlot", "VTPlot"]

_CORNER_STYLES = {"typ": "-", "min": "--", "max": ":"}
_SIDE_COLORS = {"down": "tab:blue", "up": "tab:red"}


class _PlotWidget(QWidget):
    "A matplotlib plot with its toolbar and corner check boxes."

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.figure = Figure(figsize=(6, 4), layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.axes = self.figure.add_subplot()
        self.corner_boxes: dict[str, QCheckBox] = {}
        controls = QHBoxLayout()
        for corner in _CORNER_STYLES:
            box = QCheckBox(corner)
            box.setChecked(True)
            box.toggled.connect(self._redraw)
            self.corner_boxes[corner] = box
            controls.addWidget(box)
        controls.addStretch()
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(NavigationToolbar2QT(self.canvas, self))
        layout.addWidget(self.canvas)

    @property
    def has_data(self) -> bool:
        "Whether there's anything to plot."
        raise NotImplementedError

    @property
    def shown_labels(self) -> list[str]:
        "The labels of the traces drawn now (not the rail markers)."
        return [str(line.get_label()) for line in self.axes.get_lines() if not str(line.get_label()).startswith("_")]

    def _corners(self) -> set[str]:
        return {corner for corner, box in self.corner_boxes.items() if box.isChecked()}

    def _redraw(self) -> None:
        raise NotImplementedError

    def _finish(self, title: str, xlabel: str, ylabel: str, empty: str) -> None:
        ax = self.axes
        ax.set_title(title)
        if ax.get_lines():
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.grid(True)
            ax.legend(fontsize="small")
        else:
            ax.text(0.5, 0.5, empty, ha="center", va="center", transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
        self.canvas.draw_idle()


class IVPlot(_PlotWidget):
    """One side of a model's I-V curves (``IVData.series()``, ground-referenced): ``down`` is the pulldown (or
    GND clamp), ``up`` the pullup (or POWER clamp). Typ solid, min dashed, max dotted; ``NA`` corners aren't drawn."""

    def __init__(self, iv_data: Optional[IVData] = None, side: IVSide = "down",
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.side = side
        self.set_data(iv_data)

    @property
    def title(self) -> str:
        "``Pulldown``/``Pullup``, or ``GND Clamp``/``POWER Clamp`` for a model without drivers."
        driver = self.iv_data is None or self.iv_data.is_driver
        if self.side == "down":
            return "Pulldown" if driver else "GND Clamp"
        return "Pullup" if driver else "POWER Clamp"

    @property
    def has_data(self) -> bool:
        return self.iv_data is not None and any(t.side == self.side for t in self.iv_data.series())

    def set_data(self, iv_data: Optional[IVData]) -> None:
        "Show these curves' side (``None``: none)."
        self.iv_data = iv_data
        self._redraw()

    def _redraw(self) -> None:
        self.axes.clear()
        corners = self._corners()
        if self.iv_data is not None:
            for trace in self.iv_data.series():
                if trace.side == self.side and trace.corner in corners:
                    self.axes.plot(trace.v, trace.i, _CORNER_STYLES[trace.corner], color=_SIDE_COLORS[self.side],
                                   label=trace.corner)
        if self.iv_data is not None and self.axes.get_lines():
            self._draw_rails(self.iv_data, corners)
        v_label = self.iv_data.v_label if self.iv_data else "V (V)"
        i_label = self.iv_data.i_label if self.iv_data else "I (A)"
        self._finish(f"{self.title} I-V", v_label, i_label, f"No {self.title} I-V data")

    def _draw_rails(self, iv_data: IVData, corners: set[str]) -> None:
        """Shade the rails (0 V to typ Vcc) and mark each shown corner's Vcc in that corner's line style.

        Markers are labelled with a leading ``_``, so the legend and ``shown_labels`` leave them out.
        """
        ax = self.axes
        ax.axvspan(0.0, iv_data.vdd, color="0.5", alpha=0.08, lw=0, label="_rails")
        for corner in ("typ", "min", "max"):
            if corner in corners:
                ax.axvline(iv_data.supply(corner), color="0.45", lw=0.8, ls=_CORNER_STYLES[corner],  # type: ignore[arg-type]
                           label=f"_vcc_{corner}")
        ax.text(iv_data.vdd, 1.0, " Vcc", transform=ax.get_xaxis_transform(), ha="left", va="top", fontsize="small",
                color="0.35")


class VTPlot(_PlotWidget):
    """One direction of a model's V-T waveforms (``VTWaveform.series()``): one color per fixture, typ solid,
    min dashed, max dotted."""

    def __init__(self, waveforms: Sequence[VTWaveform] = (), direction: VTDirection = "rising",
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.direction: Literal["rising", "falling"] = direction
        self.set_waveforms(waveforms)

    @property
    def title(self) -> str:
        "``Rising`` or ``Falling``."
        return self.direction.capitalize()

    @property
    def has_data(self) -> bool:
        return bool(self.waveforms)

    def set_waveforms(self, waveforms: Sequence[VTWaveform]) -> None:
        "Show these tables (only those of this direction)."
        self.waveforms = [wave for wave in waveforms if wave.direction == self.direction]
        self._redraw()

    def _redraw(self) -> None:
        self.axes.clear()
        corners = self._corners()
        for ix, wave in enumerate(self.waveforms):
            for trace in wave.series():
                if trace.corner in corners:
                    self.axes.plot(trace.t * 1e9, trace.v, _CORNER_STYLES[trace.corner], color=f"C{ix % 10}",
                                   label=trace.label.removeprefix(f"{self.title}, "))  # The tab says which.
        self._finish(f"{self.title} Waveforms", "Time (ns)", "V (V)", f"No [{self.title} Waveform] tables")
