"""
Low level helper routines used by the API functions in ``pyibisami.testing.ami_tests``.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   April 3, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

from abc import abstractmethod
from random     import randrange
from tempfile   import NamedTemporaryFile
from typing     import Protocol

import numpy as np

from matplotlib.figure      import Figure
from reportlab.lib.units    import inch
from reportlab.platypus     import Flowable, Image, Paragraph, Spacer
from scipy.signal           import convolve

from ..common           import Rvec
from ..ami.model        import AMIModel, AMIModelInitializer, OUT_RESP_INIT
from ..ami.parser       import AMIParamConfigurator

from ..util.plot        import (
    RGB, RED, GREEN, BLUE, PLOT_COLOR, PLOT_LINESTYLE,
    plt, color_picker, do_samples_per_bit,
    plot_dfe_adaptation, plot_model_results, plot_resps)
from ..util.reportlab   import P, preformatted

from .test_defs         import TestSweep

FIG_X_DFLT = 6
FIG_Y_DFLT = 4

spacer = Spacer(1, 0.25*inch)


class AmiTestHelper(Protocol):
    "Abstract class defining the function signature for AMI test helper functions."

    @abstractmethod
    def ami_tst_helper(
        self,
        model: AMIModel, initializer: AMIModelInitializer, nbits: int, label: str,
        color: RGB = BLUE, fig_x: float = FIG_X_DFLT, fig_y: float = FIG_Y_DFLT,
        plot_t_max: float = 1e-9,
    ) -> Figure:
        """
        Perform some test on an ``AMIModel`` instance.

        Args:
            model: The AMI model to test.
            initializer: The AMI model initializer to use.
            nbits: The number of bits to use for model characterization.
            label: Plot label to use.

        Keyword Args:
            color: Color to use for plot trace(s).
                Default: ``BLUE``
            fig_x: x-dimension of resultant plot figure (in.).
                Default: ``FIG_X_DFLT``
            fig_y: y-dimension of resultant plot figure (in.).
                Default: ``FIG_Y_DFLT``
            plot_t_max: Max. x-axis value (s).
                Default: 1 ns

        Returns:
            The plotting figure.
        """

        raise NotImplementedError


class AmiTestHelperInitVsGetwave():
    "Compares the output of ``AMI_Init()`` and ``AMI_GetWave()``."

    def __init__(self, debug: bool = False):
        self._debug = debug

    def ami_tst_helper(
        self,
        model: AMIModel, initializer: AMIModelInitializer, nbits: int, label: str,
        color: RGB = BLUE, fig_x: float = FIG_X_DFLT, fig_y: float = FIG_Y_DFLT, plot_t_max: float = 1e-9,
    ) -> Figure:

        model.initialize(initializer)
        model_resps = [
            ((model.get_responses(nbits=nbits, debug=self._debug), label),     # Labelled model responses.
             ({PLOT_COLOR: "blue",                             # Init() plot style.
               PLOT_LINESTYLE: "solid"},
              {PLOT_COLOR: "blue",                             # GetWave() plot style.
               PLOT_LINESTYLE: "dashed"}))]

        fig = plt.figure(figsize=(fig_x, fig_y))
        top_fig, bottom_fig = fig.subfigures(2, 1)
        top_fig.suptitle("Model Responses (Post-Adaptation)")
        top_fig.subplots_adjust(left=.1, right=.9, wspace=.3)
        bottom_fig.subplots_adjust(top=.7, bottom=.1)

        plot_model_results(model_resps, top_fig, plot_t_max)

        ax = bottom_fig.subplots(1,1)
        plot_dfe_adaptation(model.getwave_step_response_out_params, ax)

        return fig


class AmiTestHelperSamplesPerBit():
    "Probes the effect of changing the number of samples per bit."

    def ami_tst_helper(
        self,
        model: AMIModel, initializer: AMIModelInitializer, nbits: int, label: str,
        color: RGB = BLUE, fig_x: float = FIG_X_DFLT, fig_y: float = FIG_Y_DFLT,
        plot_t_max: float = 1e-9,
    ) -> Figure:

        model_responses = do_samples_per_bit(model, initializer, nbits)
        
        fig = plt.figure(figsize=(fig_x, fig_y))
        top_fig, bottom_fig = fig.subfigures(2, 1)
        top_fig.suptitle("Model Responses (Post-Adaptation)")
        top_fig.subplots_adjust(left=.1, right=.9, wspace=.3)
        bottom_fig.subplots_adjust(top=.7, bottom=.1)
        model_resps = [
            ((model_response, f"{osf}x"),
             ({PLOT_COLOR: f"{color}",
               PLOT_LINESTYLE: "solid"},
              {PLOT_COLOR: f"{color}",
               PLOT_LINESTYLE: "dashed"}
             )
            ) for (model_response, osf), color in zip(model_responses, [RED, GREEN, BLUE])
        ]
        plot_model_results(model_resps, top_fig, plot_t_max) #, debug=True)

        ax = bottom_fig.subplots(1,1)
        plot_dfe_adaptation(model.getwave_step_response_out_params, ax)

        return fig


class AmiTestHelperGetwaveInputLength():
    "Probes the effect of changing the number of bits per ``GetWave()`` call."

    def ami_tst_helper(
        self,
        model: AMIModel, initializer: AMIModelInitializer, nbits: int, label: str,
        color: RGB = BLUE, fig_x: float = FIG_X_DFLT, fig_y: float = FIG_Y_DFLT,
        plot_t_max: float = 1e-9,
    ) -> Figure:

        sample_interval = initializer.sample_interval
        channel_response = np.array(initializer.channel_response)
        bit_time = initializer.bit_time
        nspui = int(bit_time / sample_interval)
        if "Ignore_Bits" in model.info_params:
            ignore_bits = model.info_params["Ignore_Bits"].pvalue
        else:
            ignore_bits = 0

        # Assemble complete input vector, including bits to be ignored.
        u = (np.array([randrange(2) for _ in range(ignore_bits + nbits)]) * 2 - 1).repeat(nspui)
        len_u = len(u)
        w = convolve(u, channel_response * sample_interval)[:len_u]

        # Construct time/frequency vectors appropriate for indexing final output
        # (i.e. - w/o the ignored bits).
        n_kept_samples = nbits * nspui
        t = np.arange(n_kept_samples) * sample_interval
        f0 = 1 / (sample_interval * n_kept_samples)
        f = np.arange(n_kept_samples // 2 + 1) * f0  # Assumes use of `rfft()`.
        fig = plt.figure(figsize=(fig_x, fig_y))
        model.initialize(initializer)
        for bits_per_call in [randrange(8, 512) for n in range(5)] + [511, 513]:
            input_len = bits_per_call * nspui
            smpl_cnt = 0
            ys = np.array([])
            while smpl_cnt < len_u:
                if smpl_cnt + input_len > len_u:
                    x = w[smpl_cnt :]
                else:
                    x = w[smpl_cnt : smpl_cnt + input_len]
                y, _, _ = model.getWave(x)
                assert not any(np.isnan(y)), RuntimeError(
                    f"any(np.isnan(x)): {any(np.isnan(x))}")
                ys = np.concatenate((ys, y))
                smpl_cnt += input_len
            ys = ys[-n_kept_samples:]  # Drop ignored bits.
            plt.subplot(121)
            plt.plot(t * 1e9, ys, label=f"{bits_per_call}")
            plt.subplot(122)
            Ys = np.fft.rfft(ys)
            plt.semilogx(f / 1e9, 20 * np.log10(np.abs(Ys)), label=str(bits_per_call))
        
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

        return fig


def mk_linearity_checker(
    hs: list[Rvec],
    plot_t_max: float = 1e-9
) -> AmiTestHelper:
    """
    Make a model linearity checking function w/ call signature needed by ``plot_sweeps_multi()``.

    Args:
        hs: The list of channel responses to use.

    Keyword Args:
        plot_t_max: Maximum x-axis value (s).
            Default: 1 ns

    Returns:
        A function suitable for use w/ ``plot_sweeps_multi()``.
    """

    def check_linearity(
        model: AMIModel,
        initializer: AMIModelInitializer,
        nbits: int,  # Unused; to satisfy type signature of `plot_sweeps_multi()` only.
        fig: Figure,
        label: str,
    ) -> None:
        "Compare sum of model's responses to model's response to sum."

        row_size        = initializer.row_size

        hs_sum = sum(hs) / len(hs)
        initializer.channel_response = hs_sum
        model.initialize(initializer)
        t_sum, _, s_sum, p_sum, f_sum, H_sum = model.get_responses(calc_getw=False)[OUT_RESP_INIT]
        s_tot = np.zeros(row_size)
        p_tot = np.zeros(row_size)
        H_tot = np.zeros(row_size // 2 + 1) * 1j
        for h, clrs in zip(hs, color_picker(len(hs))):
            initializer.channel_response = h
            model.initialize(initializer)
            _, _, _s, _p, _, _H = model.get_responses(calc_getw=False)[OUT_RESP_INIT]
            s_tot += _s
            p_tot += _p
            H_tot += _H
        s_tot /= len(hs)
        p_tot /= len(hs)
        H_tot /= len(hs)

        # plt.figure(fig)
        blue_pair = ({PLOT_COLOR: f"{BLUE}"}, {PLOT_COLOR: f"{BLUE}"})
        red_pair  = ({PLOT_COLOR: f"{RED}"},  {PLOT_COLOR: f"{RED}"})
        left_ax, right_ax = fig.subplots(1, 2)
        plot_resps(left_ax, right_ax, {OUT_RESP_INIT: (t_sum, hs_sum, s_sum, p_sum, f_sum, H_sum)},   # type: ignore
                   "Response to Sum", blue_pair)
        plot_resps(left_ax, right_ax, {OUT_RESP_INIT: (t_sum, hs_sum, s_tot, p_tot, f_sum, H_tot)},   # type: ignore
                   "Sum of Responses", red_pair)

    class AmiTestHelperLinearityChecker(AmiTestHelper):
        def ami_tst_helper(
            self,
            model: AMIModel, initializer: AMIModelInitializer, nbits: int, label: str,
            color: RGB = BLUE, fig_x: float = 6, fig_y: float = 4, plot_t_max: float = 1e-9,
        ) -> Figure:
            fig = plt.figure(figsize=(fig_x, fig_y))
            check_linearity(model, initializer, nbits, fig, label)
            return fig

    return AmiTestHelperLinearityChecker()


def plot_sweep(
    helper: AmiTestHelper, ami_model: AMIModel,
    pcfg: AMIParamConfigurator, test_sweep: type[TestSweep],
    fig_x: float = FIG_X_DFLT, fig_y: float = FIG_Y_DFLT
) -> list[Flowable]:
    """
    Plot results of sweeping the parameters of the given AMI model,
    using the given ``TestSweep`` instance and test helper.

    Args:
        helper: The AMI test helper to use.
        ami_model: The AMI model to test.
        pcfg: The parameter configurator to use for model initialization.
        test_sweep: The ``TestSweep`` instance containing the desired parameter sweep.

    Keyword Args:
        fix_x: x-dimmension of plot (in.).
            Default: ``FIG_X_DFLT``
        fix_y: y-dimmension of plot (in.).
            Default: ``FIG_Y_DFLT``

    Returns:
        A list of _ReportLab_ ``Flowable``s, alternating between

        - a _ReportLab_ ``Paragraph`` containing the sweep description, and
        - a _ReportLab_ ``Image`` containing the plots for the described sweep.

    """

    flowables: list[Flowable] = []
    for test_def in test_sweep().test_sweep():
        p = Paragraph(preformatted(f"\t{test_def.description}:"), P)
        p.keepWithNext = True
        flowables.append(p)
        initializer = pcfg.get_init(
            test_def.sim_params["bit_time"],
            test_def.sim_params["sample_interval"],
            test_def.sim_params["channel_response"],
            test_def.ami_params
        )
        # ToDo: Get rid of `nbits`:
        helper.ami_tst_helper(ami_model, initializer, test_def.sim_params["nbits"], "")
        # plt.tight_layout()  # Doesn't work w/ subfigures.
        with NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            plt.savefig(tmp_file)
            flowables.append(Image(tmp_file.name, width=fig_x*inch, height=fig_y*inch))
        plt.close()
        flowables.append(spacer)
    return flowables
