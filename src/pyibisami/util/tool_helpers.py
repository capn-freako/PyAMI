"""
Common helper utilities used by the various scripts in ``tools/``.

Original Author: David Banas <capn.freako@gmail.com>
Original Date:   March 20, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

from typing import Generator, NewType

import numpy as np

EPS = 0.0001  # Used to test floats for "== 0".

RGB = NewType("RGB", tuple[float, float, float])


def plot_name(tst_name: str, n: int = 0) -> Generator[str, None, None]:
    """
    Plot name generator keeps multiple tests from overwriting each other's plots.

    Args:
        tst_name: The root name to use for the plot names generated.

    Keyword Args:
        n: The starting index to use for generated plot names.
            Default = 0

    Returns:
        Plot name generator.

    Notes:
        1. Plot name indices will begin at: ``n + 1``.
    """
    while True:
        n += 1
        yield f"{tst_name}_plot_{n}.png"


def hsv2rgb(hue: float, saturation: float, value:float) -> RGB:
    """
    Convert a hue-saturation-value (HSV) triple to a red-green-blue (RGB) triple.

    Args:
        hue: The hue, as a direction on the standard color wheel (deg.).
        saturation: The saturation, normalized to: [0, 1].
        value: The value (a.k.a. - brightness), normalized to: [0, 1].

    Returns:
        A 3-tuple containing the

        - red,
        - green, and
        - blue values,

        all normalized to: [0, 1].

    Notes:
        1. ``saturation`` and ``value`` are clipped to the range: [0, 1].
        2. ``hue`` is taken modulus 360.
    """

    V = min(1.0, max(0.0, float(value)))
    S = min(1.0, max(0.0, float(saturation)))
    if S < EPS:           # saturation == 0?
        return RGB((V, V, V))  # gray at brightness = `value`
    H, f = np.divmod(float(hue) % 360.0, 60.0)

    p: float = V * (1.0 - S)
    q: float = V * (1.0 - f * S)
    t: float = V * (1.0 - (1.0 - f) * S)

    match(int(H)):
        case 0:
            R = V
            G = t
            B = p
        case 1:
            R = q
            G = V
            B = p
        case 2:
            R = p
            G = V
            B = t
        case 3:
            R = p
            G = q
            B = V
        case 4:
            R = t
            G = p
            B = V
        case _:
            R = V
            G = p
            B = q

    return RGB((R, G, B))


def color_picker(num_hues: int = 3, first_hue: float = 0.0) -> Generator[tuple[RGB, RGB], None, None]:
    """
    Yields pairs of colors having the same hue, but different intensities.

    Keyword Args:
        num_hues: The number of hues into which to split the color wheel evenly.
            Default = 3
        first_hue: The desired first hue.
            Default = 0.0

    Notes:
        1. The first color is fully bright and saturated, and the second is
        half bright and half saturated. Originally, the intent was to have
        the second color used for the `reference` waveform in plots.
    """

    hue = first_hue
    hues_fetched: int = 0
    while True:
        yield (hsv2rgb(hue, 1.0, 1.0), hsv2rgb(hue, 0.75, 0.75))
        hues_fetched += 1
        if hues_fetched == num_hues:
            return
        hue += 360 // num_hues
