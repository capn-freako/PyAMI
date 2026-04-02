"""
Common helper utilities used by the various scripts in ``tools/``.

Original Author: David Banas <capn.freako@gmail.com>
Original Date:   March 20, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

import numpy as np

from pathlib    import Path
from tempfile   import NamedTemporaryFile
from typing     import Any, Callable, Generator, NewType

from matplotlib import pyplot as plt
from matplotlib.figure import Figure
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Flowable, Image, Paragraph

from ..common import TestSweep
from ..ami.model import AMIModel, AMIModelInitializer

EPS = 0.0001  # Used to test floats for "== 0".

RGB = NewType("RGB", tuple[float, float, float])

RED   = RGB((1.0, 0.0, 0.0))
GREEN = RGB((0.0, 1.0, 0.0))
BLUE  = RGB((0.0, 0.0, 1.0))
WHITE = RGB((1.0, 1.0, 1.0))
BLACK = RGB((0.0, 0.0, 0.0))

try:
    plt.rcParams['axes.titlesize'] = 8
    plt.rcParams['xtick.labelsize'] = 7
    plt.rcParams['ytick.labelsize'] = 7
    plt.rcParams['axes.labelsize'] = 7
except:
    print(f"Available keys: {plt.rcParams.keys()}")

styles = getSampleStyleSheet()


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


def plot_resps(
    fig: Figure,
    resps: dict[str, Any],
    lbl: str,
    clr: RGB
) -> None:
    """
    Plot one or two sets of responses.

    Args:
        fig: The plot figure to target.
        resps: The model responses to plot.
        lbl: The plot label to use.
        clrs: The plot hue to use, in bright and dim intensities.
    """

    plt.figure(fig)
    color_bright = "#%02X%02X%02X" % (int(clr[0] * 0xFF),
                                      int(clr[1] * 0xFF),
                                      int(clr[2] * 0xFF))
    color_dim    = "#%02X%02X%02X" % (int(0.5 * clr[0] * 0xFF),
                                      int(0.5 * clr[1] * 0xFF),
                                      int(0.5 * clr[2] * 0xFF))
    if 'out_resp_init' in resps:
        t, h, s, p, f, H = resps['out_resp_init']
        plt.subplot(121)
        plt.plot(t*1e9, s, label=lbl, color=color_dim)
        plt.plot(t*1e9, p, label=lbl, color=color_bright)
        plt.subplot(122)
        plt.semilogx(f / 1e9, 20 * np.log10(np.abs(H)), label=lbl, color=color_bright)
    if 'out_resp_getw' in resps:
        t, h, s, p, f, H = resps['out_resp_getw']
        plt.subplot(121)
        plt.plot(t*1e9, s, linestyle='dashed', color=color_dim)
        plt.plot(t*1e9, p, linestyle='dashed', color=color_bright)
        plt.subplot(122)
        plt.semilogx(f / 1e9, 20 * np.log10(np.abs(H)), linestyle='dashed', color=color_bright)


def init_vs_getwave(
    model: AMIModel,
    initializer: AMIModelInitializer,
    fig: Figure,
    color: RGB,
    label: str,
) -> None:
    """
    Run the `AMI_Init()` vs. `AMI_GetWave()` comparison,
    for a particular AMI parameter sweep program.

    Args:
        model: The AMI model to test.
        initializer: The AMI model initializer to use.
        fig: Plotting figure to use.
        color: Plot color to use.
        label: Plot label to use.

    Returns:
        Nothing
    """

    model.initialize(initializer)
    plot_resps(fig, model.get_responses(), label, color)


def plot_sweeps(
    func: Callable[[AMIModel, AMIModelInitializer, Figure, RGB, str], None],
    model: AMIModel,
    initializer: AMIModelInitializer,
    sweeps: list[TestSweep],
    fig_x: float = 6,
    fig_y: float = 2,
    plot_t_max: float = 1e-9
) -> list[Flowable]:
    """
    Run a common testing/plotting function over several parameter sweeps.

    Args:
        func: Testing/plotting function.
        model: AMI model to test.
        initializer: AMI model initializer to use/modify.
        sweeps: Parameter sweep definitions.

    Keyword Args:
        fix_x: x-dimmension of plot (in.).
            Default: 6
        fix_y: y-dimmension of plot (in.).
            Default: 1.5
        plot_t_max: Plot time axis right bound (s).
            Default: 1 ns

    Returns:
        A list of _ReportLab_ ``Flowable``s, alternating between

        - a _ReportLab_ ``Paragraph`` containing the sweep description, and
        - a _ReportLab_ ``Image`` containing the plots for the described sweep.
    """

    rslts = []
    for sweep in sweeps:
        cfg_name    = sweep[0]
        description = sweep[1]
        cfg_list    = sweep[2]
        colors      = color_picker(num_hues=len(cfg_list))

        desc = f"Running sweep `{cfg_name}`: {description}"
        fig = plt.figure(figsize=(fig_x, fig_y))
        # Accommodating both new and old style IBIS-AMI model configuration:
        for color, fields in zip(colors, cfg_list):
            label = fields[0]
            ami_params = fields[1][0]
            sim_params = fields[1][1]
            initializer.ami_params.update(ami_params)
            if "channel_response" in sim_params:
                initializer.channel_response = sim_params["channel_response"]
            if "row_size" in sim_params:
                initializer.row_size = sim_params["row_size"]
            if "num_aggressors" in sim_params:
                initializer.num_aggressors = sim_params["num_aggressors"]
            if "sample_interval" in sim_params:
                initializer.sample_interval = sim_params["sample_interval"]
            if "bit_time" in sim_params:
                initializer.bit_time = sim_params["bit_time"]
            func(model, initializer, fig, color[0], label)

        plt.subplot(121)
        plt.axis(xmin=-0.1, xmax=plot_t_max*1e9)
        plt.title("Step & Pulse Resp. (V)")
        plt.xlabel("Time (ns)")
        plt.grid()
        plt.subplot(122)
        plt.title("Frequency Resp. (dB)")
        plt.xlabel("Frequency (GHz)")
        plt.grid()
        plt.tight_layout()

        # ToDo: Can we figure out how to comment out the `delete=False` line below?
        with NamedTemporaryFile(suffix='.jpg', prefix=(cfg_name),
                                delete_on_close=False,  # Deleted after use in a context manager.
                                delete=False,           # Debugging missing files.
                               ) as tmp_file:
            plt.savefig(tmp_file)
            rslts.extend([Paragraph(desc, styles['Normal']),
                          Image(tmp_file.name, width=(fig_x)*inch, height=(fig_y)*inch)])

    return rslts
