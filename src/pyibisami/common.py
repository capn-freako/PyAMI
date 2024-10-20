"""
Definitions common to all PyIBIS-AMI modules.

Original author: David Banas <capn.freako@gmail.com>

Original date:   May 15, 2024

Copyright (c) 2024 David Banas; all rights reserved World wide.
"""

import numpy.typing as npt  # type: ignore
from scipy.linalg import convolution_matrix, lstsq
from typing_extensions import TypeAlias, TypeVar

Real = TypeVar("Real", float, float)
Comp = TypeVar("Comp", complex, complex)
Rvec: TypeAlias = npt.NDArray[Real]
Cvec: TypeAlias = npt.NDArray[Comp]
# Rvec = npt.NDArray[Real]
# Cvec = npt.NDArray[Comp]

# PI: float = np.pi  # Causes a failed import of `pyibisami.ami.model` during `tox -e docs`, due to:
#   File "C:\Users\davibana\prj\PyBERT\PyAMI\src\pyibisami\common.py", line 23, in <module>
#     TWOPI = 2. * PI
# TypeError: unsupported operand type(s) for *: 'float' and 'pi'
# Why?! And what is 'pi'?!

PI: float = 3.141592653589793238462643383279502884
TWOPI: float = 2.0 * PI


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
