"""
Low level helper routines used by the API functions in ``pyibisami.testing.ami_tests``.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   April 3, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

from random     import randrange
from tempfile   import NamedTemporaryFile
from typing     import Any, Callable

import numpy as np

from matplotlib.figure      import Figure
from reportlab.lib.units    import inch
from reportlab.platypus     import Flowable, Image, ListFlowable, ListItem, PageBreak, Paragraph, Spacer
from scipy.interpolate      import interp1d

from ..common           import Rvec, TestSweep
from ..ami.model        import AMIModel, AMIModelInitializer
from ..util.plot        import RGB, RED, GREEN, BLUE, plt, color_picker
from ..util.reportlab   import ital, styles


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


def do_samples_per_bit(
    model: AMIModel, initializer: AMIModelInitializer, channel_response: Rvec,
    sample_interval: float, bit_rate: float, nbits: int
) -> list[tuple[dict[str, Any], int]]:
    """
    Run the "Samples per Bit" comparison.

    Args:
        model: The AMI model to test.
        initializer: The AMI model initializer to use/customize.
        channel_response: The analog channel impulse response.
        sample_interval: The time spacing between successive elements of ``channel_response``.
        bit_rate: The assumed symbol rate.
        nbits: The number of bits to use for model characterization.

    Returns:
        A list of model response dictionaries, one for each oversampling rate tried.
    """

    # Do not interpolate deltas.
    len_ch_resp = len(channel_response)
    t = np.arange(0, len_ch_resp) * sample_interval
    nspui = int(1 / (sample_interval * bit_rate))

    def interp(x, ts):
        if not any(channel_response[1:]):  # delta?
            len_x = len(x)
            if len_x > len_ch_resp:
                rslt = np.pad(channel_response, (0, len_x - len_ch_resp),
                           mode="constant", constant_values=0)
            else:
                rslt = channel_response[:len_x]
            return rslt * sample_interval / ts
        else:
            krnl = interp1d(
                t, channel_response, kind="cubic",
                bounds_error=False, fill_value="extrapolate", assume_sorted=True
            )  # interpolation "kernel"
            return krnl(x)

    model_responses = []
    for osf in [nspui//2, nspui, nspui*2]:
        ts = 1 / (bit_rate * osf)
        _row_size = nbits * osf
        _t = np.array([n * ts for n in range(_row_size)])
        
        initializer.sample_interval = ts
        initializer.channel_response = interp(_t, ts)
        model.initialize(initializer)
        model_responses.append((model.get_responses(), osf))

    return model_responses


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
