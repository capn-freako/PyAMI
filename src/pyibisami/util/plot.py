"""
General purpose utilities for plot construction.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   April 3, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

from dataclasses import dataclass
from typing import Any, Generator, Optional, NewType, Sequence, TypeAlias

from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import numpy as np
from scipy.interpolate import interp1d

from ..common import EPS, Rvec
from ..ami.model import (
    AMIModel, AMIModelInitializer, AmiModelResponses,
    IMP_RESP_INIT, OUT_RESP_INIT, IMP_RESP_GETW, OUT_RESP_GETW
)

from .ami import get_dfe_adaptation


@dataclass(frozen=True)
class RGB:
    "Color defined by 3 floats in [0, 1]: red, green, and blue."

    color: tuple[float, float, float]

    def __post_init__(self):
        if not isinstance(self.color, tuple) or len(self.color) != 3:
            raise TypeError("Color must be a triple of floats.")
        if any(color < 0 for color in self.color) or any(color > 1 for color in self.color):
            raise ValueError("All color components must be in [0, 1].")

    def __str__(self):
        return "#%02X%02X%02X" % (int(self.color[0] * 0xFF),
                                  int(self.color[1] * 0xFF),
                                  int(self.color[2] * 0xFF))


RED   = RGB((1.0, 0.0, 0.0))
GREEN = RGB((0.0, 1.0, 0.0))
BLUE  = RGB((0.0, 0.0, 1.0))
WHITE = RGB((1.0, 1.0, 1.0))
BLACK = RGB((0.0, 0.0, 0.0))

LabelledModelResponses: TypeAlias = tuple[AmiModelResponses, str]

VALID_STYLE_FEATURES = [
    "color",
    "linestyle",
    "marker",
    "fontsize",
    "fontweight",
    "fontstyle",
]

@dataclass(frozen=True)
class PlotStyleFeature:
    "A string constrained to valid Matplotlib plot style feature names."

    feature: str

    def __post_init__(self):
        if not isinstance(self.feature, str):
            raise TypeError("Feature must be a string.")
        if not self.feature in VALID_STYLE_FEATURES:
            raise ValueError(f"Feature must be one of:\n{VALID_STYLE_FEATURES}")

    def __str__(self):
        return feature

PlotStyle: TypeAlias = dict[PlotStyleFeature, str]

PLOT_COLOR = PlotStyleFeature("color")
PLOT_LINESTYLE = PlotStyleFeature("linestyle")
PLOT_MARKER = PlotStyleFeature("marker")
PLOT_FONTSIZE = PlotStyleFeature("fontsize")
PLOT_FONTWEIGHT = PlotStyleFeature("fontweight")
PLOT_FONTSTYLE = PlotStyleFeature("fontstyle")

plt.rcParams['axes.titlesize'] = 10
plt.rcParams['xtick.labelsize'] = 7
plt.rcParams['ytick.labelsize'] = 7
plt.rcParams['axes.labelsize'] = 8


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
    f /= 60
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
    left_ax: Axes,
    right_ax: Axes,
    resps: AmiModelResponses,
    lbl: str,
    styles: Optional[tuple[PlotStyle, PlotStyle]] = None,
    debug: bool = False
) -> None:
    """
    Plot IBIS-AMI model responses.

    Args:
        left_ax: The left plot axes to target.
        right_ax: The right plot axes to target.
        resps: The model responses to plot.
        lbl: The plot label to use.

    Keyword Args:
        styles: Optional pair of styles to use for ``Init()``/``GetWave()`` plotting.
            Default: None (blue solid/dashed will be used.)
        debug: Print debugging info when ``True``.
            Default: ``False``
    """

    if debug:
        print(f"lbl: {lbl}")
    # Define the defaults.
    init_color = "blue"
    getwave_color = "blue"
    init_linestyle = "solid"
    getwave_linestyle = "dashed"
    # And override them if they're available.
    if styles:
        init_style, getwave_style = styles
        init_color = init_style.get(PLOT_COLOR, init_color)
        getwave_color = getwave_style.get(PLOT_COLOR, getwave_color)
        init_linestyle = init_style.get(PLOT_LINESTYLE, init_linestyle)
        getwave_linestyle = getwave_style.get(PLOT_LINESTYLE, getwave_linestyle)
    if debug:
        print(f"init_color: {init_color}")
    # Do the plotting.
    if OUT_RESP_INIT in resps:
        if debug:
            print("Plotting OUT_RESP_INIT...")
        t, h, s, p, f, H = resps[OUT_RESP_INIT]
        left_ax.plot(t*1e9, s,            color=init_color, linestyle=init_linestyle,)
        left_ax.plot(t*1e9, p, label=lbl, color=init_color, linestyle=init_linestyle,)
        right_ax.semilogx(f / 1e9, 20 * np.log10(np.abs(H)), label=lbl,
                          color=init_color, linestyle=init_linestyle,)
    if OUT_RESP_GETW in resps:
        t, h, s, p, f, H = resps[OUT_RESP_GETW]
        left_ax.plot(t*1e9, s, color=getwave_color, linestyle=getwave_linestyle,)
        left_ax.plot(t*1e9, p, color=getwave_color, linestyle=getwave_linestyle,)
        right_ax.semilogx(f / 1e9, 20 * np.log10(np.abs(H)),
                          color=getwave_color, linestyle=getwave_linestyle)


def plot_dfe_adaptation(
    getwave_out_params: Optional[list[str]],
    ax: Axes
) -> None:
    """
    Plot DFE tap weight adaptation from ``GetWave()`` output parameters.

    Args:
        getwave_out_params: List of AMI output parameters from multiple ``GetWave()`` calls.
        ax: Matplotlib axes to use for plotting.
    """

    if not getwave_out_params:
        return

    dfe_adaptation = get_dfe_adaptation(getwave_out_params)
    dfe_adaptation_keys = list(dfe_adaptation.keys())
    dfe_adaptation_keys.sort()
    for key in dfe_adaptation_keys:
        ax.plot(dfe_adaptation[key], label=key)
    ax.set_title("DFE Adaptation")
    ax.legend()


def plot_finalize_steppulse_freq(
    fig: Figure,
    plot_t_max: float = 1e-9,
    debug: bool = False
):
    """
    Add the finishing touches to a plot of Step/Pulse & Frequency responses.

    Args:
        fig: The plot figure to finalize.

    Keyword Args:
        plot_t_max: The maximum x-axis value
            Default: 1 ns
        debug: Show the plot on screen when ``True``.
            Default: ``False``
    """

    plt.figure(fig)
    plt.subplot(121)
    plt.axis(xmin=-0.1, xmax=plot_t_max*1e9)
    plt.title("Step & Pulse Resp. (V)")
    plt.xlabel("Time (ns)")
    plt.grid()
    plt.legend()
    plt.subplot(122)
    plt.title("Frequency Resp. (dB)")
    plt.xlabel("Frequency (GHz)")
    plt.grid()
    plt.legend()
    if debug:
        plt.show()

def plot_model_results(
    model_responses: Sequence[tuple[LabelledModelResponses, Optional[tuple[PlotStyle, PlotStyle]]]],
    fig: Figure,
    plot_t_max: float = 1e-9,
    debug: bool = False
):
    """
    Plot IBIS-AMI model responses and (optionally) adaptation.

    Args:
        model_responses: List of pairs, each containing

            - labelled model responses, and
            - an optional pair of styles for ``Init()`` and ``GetWave()``.

        fig: *Matplotlib* ``Figure`` to use for plotting.

    Keyword Args:
        plot_t_max: Max. x-axis value (s).
            Default: 1 ns
        debug: Print debugging information when ``True``.
            Default: ``False``
    """

    left_ax, right_ax = fig.subplots(1, 2)
    for (model_response, label), styles in model_responses:
        if debug:
            print(f"styles: {styles}")
        plot_resps(left_ax, right_ax, model_response, label, styles=styles, debug=debug)
    plot_finalize_steppulse_freq(fig, plot_t_max, debug=debug)


def do_samples_per_bit(
    model: AMIModel, initializer: AMIModelInitializer, nbits: int
) -> list[tuple[AmiModelResponses, int]]:
    """
    Run the "Samples per Bit" comparison.

    Args:
        model: The AMI model to test.
        initializer: The AMI model initializer to use/customize.
        nbits: The number of bits to use for model characterization.

    Returns:
        A list of model response dictionaries, one for each oversampling rate tried.
    """

    channel_response = np.array(initializer.channel_response)
    sample_interval  = initializer.sample_interval
    bit_rate         = 1 / initializer.bit_time

    len_ch_resp = len(channel_response)
    t = np.arange(len_ch_resp) * sample_interval
    nspui = int(1 / (sample_interval * bit_rate))
    init_bits = len_ch_resp // nspui
    krnl = interp1d(
        t, channel_response, kind="cubic",
        bounds_error=False, fill_value="extrapolate", assume_sorted=True
    )  # interpolation "kernel"

    def interp(t):
        "Does not interpolate deltas."
        if not any(channel_response[2:]):  # delta?
            len_t = len(t)
            ts = t[1] - t[0]
            if len_t > len_ch_resp:
                rslt = np.pad(channel_response, (0, len_t - len_ch_resp),
                           mode="constant", constant_values=0)
            else:
                rslt = channel_response[:len_t]
            return rslt * sample_interval / ts
        else:
            return krnl(t)

    model_responses = []
    for osf in [nspui//2, nspui, nspui*2]:
        ts = 1 / (bit_rate * osf)
        _row_size = init_bits * osf
        _t = np.array([n * ts for n in range(_row_size)])
        
        initializer.sample_interval = ts
        initializer.channel_response = interp(_t)
        model.initialize(initializer)
        model_responses.append((model.get_responses(nbits=nbits), osf))
    initializer.sample_interval  = sample_interval
    initializer.channel_response = channel_response

    return model_responses
