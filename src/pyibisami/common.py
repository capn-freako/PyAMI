"""
Definitions common to all PyIBIS-AMI modules.

Original author: David Banas <capn.freako@gmail.com>

Original date:   May 15, 2024

Copyright (c) 2024 David Banas; all rights reserved World wide.
"""

from typing             import Any, TypeAlias, TypeVar
import numpy.typing as npt  # type: ignore
from scipy.linalg       import convolution_matrix, lstsq

Real = TypeVar("Real", float, float)
Comp = TypeVar("Comp", complex, complex)
Rvec: TypeAlias = npt.NDArray["Real"]
Cvec: TypeAlias = npt.NDArray["Comp"]

PI:    float = 3.141592653589793238462643383279502884
TWOPI: float = 2.0 * PI

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
    A = convolution_matrix(x, len(y), "same")
    h, _, _, _ = lstsq(A, y)
    return h
