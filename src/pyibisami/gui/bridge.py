"""Hand core ``Signal`` s over to the Qt GUI thread.

Core callbacks run on whichever thread changed the object (e.g. - PyBERT's optimizer thread). Widgets must only be
touched from the GUI thread, so each widget listens through a ``SignalBridge``: the core callback only emits a Qt
signal (safe from any thread), whose queued delivery restarts a short timer on the GUI thread; the timer's timeout
emits ``changed``, once per burst. Slots connected to ``changed`` re-read the core object instead of trusting the
order of the changes.

Original Author: David Patterson

Original Date:   November 5, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from ..events import Signal as CoreSignal

__all__ = ["REFRESH_MS", "SignalBridge"]

REFRESH_MS = 33  # Coalesce bursts of core changes into one refresh, at about 30 Hz.


class SignalBridge(QObject):
    """Emits ``changed`` on the GUI thread, after any of the given core signals fires (bursts coalesced).

    Disconnects from the core signals when its parent is destroyed (or on ``disconnect_all()``).
    """

    changed = Signal()
    _poked = Signal()

    def __init__(self, parent: QObject, *core_signals: CoreSignal, interval_ms: int = REFRESH_MS) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.changed)
        self._poked.connect(self._schedule, Qt.ConnectionType.QueuedConnection)
        poke = self._poke  # Holds no reference to the Qt wrapper beyond this bound method.
        self._disconnects: list[Callable[[], None]] = [sig.connect(lambda *_: poke()) for sig in core_signals]
        disconnects = self._disconnects
        parent.destroyed.connect(lambda *_: [disconnect() for disconnect in disconnects])

    def _poke(self) -> None:
        "Called from any thread."
        try:
            self._poked.emit()
        except RuntimeError:  # The Qt object is already gone.
            pass

    def _schedule(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def disconnect_all(self) -> None:
        "Stop listening to the core signals."
        for disconnect in self._disconnects:
            disconnect()
        self._disconnects.clear()
