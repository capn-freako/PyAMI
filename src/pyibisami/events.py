"""Plain-Python change notification and value errors.

Original author: David Patterson

Original date:   November 5, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["InvalidValueError", "Signal"]


class InvalidValueError(ValueError):
    "A value that isn't legal for the attribute or parameter it was given to."


class Signal:
    """A list of callbacks, called in order with the arguments given to ``emit()``.

    Callbacks run synchronously, on the emitting thread. An exception in one is logged and doesn't stop the others,
    or reach the code that emitted.

    Threads: ``connect()``, ``disconnect()`` and ``emit()`` may be called from any thread. A callback runs on the
    thread that emitted, which may be a worker thread (e.g. - an optimizer calling ``set_param_val()``): a GUI must
    hand the work to its own thread (e.g. - a queued Qt signal) before touching widgets. A callback should read the
    object's current state rather than rely on the order of the values it's given.
    """

    def __init__(self) -> None:
        self._callbacks: list[Callable[..., Any]] = []
        self._lock = threading.Lock()

    def connect(self, callback: Callable[..., Any]) -> Callable[[], None]:
        """Call ``callback`` on each ``emit()``.

        Returns:
            A function that disconnects it.
        """
        with self._lock:
            self._callbacks.append(callback)
        return lambda: self.disconnect(callback)

    def disconnect(self, callback: Callable[..., Any]) -> None:
        "Stop calling ``callback``; no error if it isn't connected."
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def emit(self, *args: Any) -> None:
        "Call every connected callback with ``args`` (not holding any lock, so a callback may connect or emit)."
        with self._lock:
            callbacks = list(self._callbacks)
        for callback in callbacks:
            try:
                callback(*args)
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Error in callback %r", callback)

    def __len__(self) -> int:
        return len(self._callbacks)
