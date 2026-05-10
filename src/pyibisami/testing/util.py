"""
General purpose utilities for the model testing infrastructure.

Original author: David Banas <capn.freako@gmail.com>

Original date: May 7, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

import inspect
from pathlib            import Path
import types
from typing             import Optional

from ..util.misc        import import_from_path

from .test_defs         import TestSweep, TestSweeper


def get_sweepers(
    mod: types.ModuleType
) -> TestSweeper:
    """
    Extract all subclasses of ``TestSweep`` from given module.

    Args:
        mod: Module from which to extract ``TestSweep`` subclasses.

    Returns:
        A pair containing

        - The given module's docstring if present, and
        - the list of ``TestSweep`` subclasses found.
    """

    return (
        mod.__doc__,
        [obj for name, obj in inspect.getmembers(mod, inspect.isclass)  # type: ignore
             if issubclass(obj, TestSweep) and not obj == TestSweep]
    )


def get_all_sweepers(
    dir: Path
) -> list[TestSweeper]:
    """
    Extract all subclasses of ``TestSweep`` from all modules in given directory.

    Args:
        dir: The directory in which to search for modules.

    Returns:
        A list of pairs, each containing:

        - A module's docstring if present, and
        - the list of ``TestSweep`` subclasses found in that module.
    """

    files = list(dir.glob("*.py"))
    if not files:
        return []
    sweepers: list[TestSweeper] = []
    for file in files:
        module = import_from_path(file.parent.stem + "." + file.stem, file)
        sweepers.append(get_sweepers(module))
    return sweepers
