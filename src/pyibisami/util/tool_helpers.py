"""
Common helper utilities used by the various scripts in ``tools/``.

Original Author: David Banas <capn.freako@gmail.com>
Original Date:   March 20, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

import numpy as np

from pathlib    import Path
from random     import randrange
from tempfile   import NamedTemporaryFile
from typing     import Any, Callable, Generator, NewType

from matplotlib import pyplot as plt
from matplotlib.figure import Figure
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Flowable, Image, PageBreak, Paragraph, Spacer

from ..common import Rvec, TestSweep
from ..ami.model import AMIModel, AMIModelInitializer

from .model_testing import do_samples_per_bit

EPS = 0.0001  # Used to test floats for "== 0".

RGB = NewType("RGB", tuple[float, float, float])

RED   = RGB((1.0, 0.0, 0.0))
GREEN = RGB((0.0, 1.0, 0.0))
BLUE  = RGB((0.0, 0.0, 1.0))
WHITE = RGB((1.0, 1.0, 1.0))
BLACK = RGB((0.0, 0.0, 0.0))

try:
    plt.rcParams['axes.titlesize'] = 10
    plt.rcParams['xtick.labelsize'] = 7
    plt.rcParams['ytick.labelsize'] = 7
    plt.rcParams['axes.labelsize'] = 8
except:
    print(f"Available keys: {plt.rcParams.keys()}")

# ReportLab Platypus abbreviations
page_break = PageBreak()
spacer = Spacer(inch, 0.15*inch)
styles = getSampleStyleSheet()
P  = styles['Normal']
H1 = styles['Heading1']
H2 = styles['Heading2']
H3 = styles['Heading3']
H4 = styles['Heading4']
bold_style = ParagraphStyle(
    name='BoldStyle',
    parent=styles['Normal'],
    fontName='Helvetica-Bold', # Specify the bold variant here
    # fontSize=12
)
caption_style = ParagraphStyle(
    name='CaptionStyle',
    parent=styles['Normal'],
    fontName='Helvetica-Bold', # Specify the bold variant here
    fontSize=10,
    alignment=TA_CENTER,
)
indented_style = ParagraphStyle(
    name='IndentedStyle',
    parent=styles['Normal'],
    leftIndent=50,
)


def tag(html_tag: str, text: str) -> str:
    """Apply given HTML tag to text."""
    return f"<{html_tag}>{text}</{html_tag}>"


def bold(text: str) -> str:
    """Embolden text, using HTML `<strong>` tag."""
    return tag("strong", text)


def ital(text: str) -> str:
    """Italicize text, using HTML `<em>` tag."""
    return tag("em", text)


def fixed(text: str) -> str:
    """Render text in fixed width font, using HTML `<pre>` tag."""
    return tag("kbd", text)


# General purpose utilities.
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
    Plot available responses.

    Args:
        fig: The plot figure to target.
        resps: The model responses to plot.
        lbl: The plot label to use.
        clrs: The plot hue to use, in full brightness.
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
        plt.plot(t*1e9, s, color=color_dim)
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


def samples_per_bit(
    model: AMIModel,
    initializer: AMIModelInitializer,
    fig: Figure,
    color: RGB,
    label: str,
) -> None:
    """
    Run the `samples per bit` comparison, for a particular AMI parameter config.

    Args:
        model: The AMI model to test.
        initializer: The AMI model initializer to use.
        fig: Plotting figure to use.
        color: Plot color to use.
            (Ignored; see below.)
        label: Plot label to use.

    Returns:
        Nothing

    Notes:
        1. The ``color`` parameter is ignored here.
        However, the function signature must be as it is, for use w/ ``plot_sweeps()``.
    """

    model_responses = do_samples_per_bit(
        model, initializer, np.array(initializer.channel_response),
        initializer.sample_interval, 1 / initializer.bit_time, 20)
    
    for ((model_response, osf), color) in zip(model_responses, [RED, GREEN, BLUE]):
        plot_resps(fig, model_response, f"{osf}x", color)


def check_getwave_input_length(
    model: AMIModel,
    initializer: AMIModelInitializer,
    fig: Figure,
    color: RGB,
    label: str,
) -> None:
    """
    Check sensitivity of ``AMI_GetWave()`` to varying input length,
    for the given channel impulse response.

    Args:
        model: The AMI model to test.
        initializer: The AMI model initializer to use.
        fig: Plotting figure to use.
        color: Plot color to use.
            (Ignored; see below.)
        label: Plot label to use.

    Returns:
        Nothing
    """

    sample_interval = initializer.sample_interval
    channel_response = initializer.channel_response
    bit_time = initializer.bit_time

    nspui = int(bit_time / sample_interval)

    u = (np.array([randrange(2) for n in range(1_000)]) * 2 - 1).repeat(nspui)
    len_u = len(u)
    t = np.array([n * sample_interval for n in range(len_u)])
    f0 = 1 / (sample_interval * len_u)
    f = np.array([n * f0 for n in range(len_u)])
    plt.figure(fig)
    model.initialize(initializer)
    for n, bits_per_call in enumerate([randrange(8, 512) for n in range(5)] + [511, 513]):
        input_len = bits_per_call * nspui
        smpl_cnt = 0
        ys = np.array([])
        while smpl_cnt < len_u:
            if smpl_cnt + input_len > len_u:
                x = u[smpl_cnt :]
            else:
                x = u[smpl_cnt : smpl_cnt + input_len]
            y, _, _ = model.getWave(x)
            ys = np.concatenate((ys, y))
            smpl_cnt += input_len
        # if n:
        plt.subplot(121)
        plt.plot(t * 1e9, ys, label=str(bits_per_call))
        plt.subplot(122)
        Ys = np.fft.fft(ys)
        plt.semilogx(f[:len_u // 2] / 1e9, 20 * np.log10(np.abs(Ys[:len_u // 2])),
                     label=str(bits_per_call))
    
    plt.subplot(121)
    plt.title("AMI_GetWave() Output")
    plt.xlabel("Time (ns)")
    plt.ylabel("Vout (V)")
    plt.axis(xmin=t[-20 * nspui] * 1e9, xmax=t[-1] * 1e9)
    plt.legend()
    plt.grid()
    
    plt.subplot(122)
    plt.title("Spectral Content")
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("|H(f)| (dB)")
    plt.legend()
    plt.grid()


def plot_sweeps(
    func: Callable[[AMIModel, AMIModelInitializer, Figure, RGB, str], None],
    model: AMIModel,
    initializer: AMIModelInitializer,
    sweeps: list[TestSweep],
    fig_x: float = 6,
    fig_y: float = 2,
    plot_t_max: float = 1e-9,
    finalize: bool = True
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
        finalize: Finish plot annotations when ``True``.
            Default: ``True``

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

        desc = f"Running sweep `{cfg_name}`: {ital(f'{description}')}"
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

        if finalize:
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
