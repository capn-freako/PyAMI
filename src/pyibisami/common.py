"""
Definitions common to all PyIBIS-AMI modules.

Original author: David Banas <capn.freako@gmail.com>

Original date:   May 15, 2024

Copyright (c) 2024 David Banas; all rights reserved World wide.
"""

from collections.abc    import Iterator
from contextlib         import contextmanager
from typing             import Any, TypeAlias, TypeVar

import numpy        as np
import numpy.typing as npt  # type: ignore

from scipy.linalg       import convolution_matrix, lstsq

Real = TypeVar("Real", float, float)
Comp = TypeVar("Comp", complex, complex)
Rvec: TypeAlias = npt.NDArray["Real"]
Cvec: TypeAlias = npt.NDArray["Comp"]

PI:    float = 3.141592653589793238462643383279502884
TWOPI: float = 2.0 * PI
EPS:   float = 0.0001  # Used to test floats for "== 0".

# ToDo: What's this about?:
# TestConfig: TypeAlias = tuple[str, tuple[dict[str, Any], dict[str, Any]]]
# TestSweep:  TypeAlias = tuple[str, str, list[TestConfig]]
TestConfig = tuple[str, tuple[dict[str, Any], dict[str, Any]]]
TestSweep = tuple[str, str, list[TestConfig]]

GUI_INSTALL_HINT = 'The PyIBIS-AMI GUI requires its optional dependencies: pip install "pyibis-ami[gui]"'


@contextmanager
def require_gui() -> Iterator[None]:
    """
    Guard the imports of the optional GUI dependencies (``traitsui``, ``chaco``, ``enable``),
    turning their absence into an ``ImportError`` that says how to install them.
    """
    try:
        yield
    except ImportError as err:
        raise ImportError(f"{GUI_INSTALL_HINT}\n({err})") from err


def deconv_same(y: Rvec, x: Rvec) -> Rvec:
    """
    Deconvolve input from output, to recover filter response, for same length I/O.

    Args:
        y: output signal
        x: input signal

    Returns:
        h: filter impulse response.
    """
    A = convolution_matrix(x, len(y), "same")
    h, _, _, _ = lstsq(A, y)
    return h


def raised_cosine(x):
    """
    Apply raised cosine filter to input.
    """
    phi = np.linspace(0, PI, len(x))
    return x * 0.5 * (np.cos(phi) + 1)
