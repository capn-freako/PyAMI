"""
Definitions common to all PyIBIS-AMI modules.

Original author: David Banas <capn.freako@gmail.com>

Original date:   May 15, 2024

Copyright (c) 2024 David Banas; all rights reserved World wide.
"""

from typing             import Any, TypeAlias, TypeVar

import numpy        as np
import numpy.typing as npt  # type: ignore

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


def deconv_same(y: Rvec, x: Rvec) -> Rvec:
    """
    Deconvolve input from output, to recover filter response, for same length I/O.

    Args:
        y: output signal
        x: input signal

    Returns:
        h: filter impulse response.
    """
    # Build the "same"-mode convolution matrix (equivalent to `scipy.linalg.convolution_matrix(x, n, "same")`):
    # the central `max(m, n)` rows of the full `(m + n - 1) x n` Toeplitz matrix, whose `[i, j]` element is `x[i - j]`.
    x = np.asarray(x)
    m = len(x)
    n = len(y)
    tb = (min(m, n) - 1) // 2
    k = np.arange(tb, tb + max(m, n))[:, None] - np.arange(n)[None, :]
    A = np.where((k >= 0) & (k < m), x[np.clip(k, 0, m - 1)], 0)
    h, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
    return h


def raised_cosine(x):
    """
    Apply raised cosine filter to input.
    """
    phi = np.linspace(0, PI, len(x))
    return x * 0.5 * (np.cos(phi) + 1)
