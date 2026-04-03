"""
Individual tests for AMI models.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   April 2, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

import platform

from abc     import ABC, abstractmethod
from pathlib import Path
from typing  import Sequence

import numpy as np

from reportlab.lib.units    import inch
from reportlab.platypus     import Flowable, Image, ListFlowable, ListItem, PageBreak, Paragraph, Spacer
from scipy.interpolate      import interp1d
from scipy.signal           import butter, freqs, lfilter

from ..common           import PI, Rvec, TestSweep, raised_cosine
from ..ami.model        import AMIModel
from ..ami.parser       import AMIParamConfigurator, ParamName
from ..ibis.model       import Model
from ..util.reportlab   import (
    bold, ital, fixed, page_break, spacer, preformatted,
    styles, bold_style, caption_style, indented_style,
    P, H1, H2, H3, H4)

from .ami_tests_helpers import init_vs_getwave, plot_sweeps, samples_per_bit, check_getwave_input_length

class AmiTester(ABC):
    "Abstract class defining the function signature for AMI testing functions."

    @abstractmethod
    def ami_tst(
        self,
        ami_model: AMIModel, pcfg: AMIParamConfigurator,
        bit_interval: float, sample_interval:float,
        channel_response: Rvec, param_defs: list[TestSweep],
        fig_x: float = 6, fig_y: float = 3,
    ) -> list[Flowable]:
        """
        Perform some test on an ``AMIModel`` instance.

        Args:
            ami_model: The AMI model to test.
            pcfg: The AMI model configurator to use/modify.
            bit_interval: The unit interval (s).
            sample_interval: Time between adjacent signal vector elements (s).
            channel_response: Analog channel impulse response (V/s).
            param_defs: List of AMI/simulation parameter sets to sweep over.

        Keyword Args:
            fig_x: x-dimension of resultant plot figure (in.).
                Default: 6
            fig_y: y-dimension of resultant plot figure (in.).
                Default: 3

        Returns:
            A list of _ReportLab_ ``Flowable``s comprising the results of this test.
        """

        raise NotImplementedError

class AmiTestInitVsGetwave(AmiTester):
    "Compare output from ``AMI_Init()`` and ``AMI_GetWave()`` functions."

    def ami_tst(
        self,
        ami_model: AMIModel, pcfg: AMIParamConfigurator,
        bit_interval: float, sample_interval:float,
        channel_response: Rvec, param_defs: list[TestSweep],
        fig_x: float = 6, fig_y: float = 3,
    ) -> list[Flowable]:
        flowables: list[Flowable] = [
            page_break,
            Paragraph("Init() vs. GetWave()", H4),
            Paragraph(
                "Here, we check to see that the fundamental responses of the model are the same \
                whether we call AMI_Init() or AMI_GetWave().", P),
            spacer,
            Paragraph(f"{bold('Note:')} This test is only possible for models that:", P),
            ListFlowable([
                Paragraph(f"have an {fixed('AMI_GetWave()')} function, and", P),
                Paragraph(f"return an impulse response from their {fixed('AMI_Init()')} function.", P),
            ], bulletType='bullet', bulletIndent=0.25*inch),
            spacer,
        ]
        initializer = pcfg.get_init(
            bit_interval, sample_interval, channel_response, {"root_name": pcfg._root_name})
        flowables.extend(plot_sweeps(init_vs_getwave, ami_model, initializer, param_defs,
                                     fig_x=fig_x, fig_y=fig_y))
        flowables.extend([
            Paragraph(f"{bold('Plot notes:')}", P),
            ListFlowable([
                Paragraph(f"Solid lines are {fixed('Init()')}; dashed are {fixed('GetWave()')}."),
                Paragraph("Step response shown at half brightness."),
            ], bulletFontSize=9),
            spacer,
            Paragraph(f"Compare the plots above. \
                      The {fixed('Init()')} (solid) and {fixed('GetWave()')} (dashed) plots \
                      should look nearly identical.", P),
            Paragraph(f"({bold('Note:')} Ignore the waveform before time zero; \
                      it`s not expected to match and is plotted only as a debugging aid.)", P),
        ])

        return flowables


class AmiTestSamplesPerBit(AmiTester):
    "Compare model response at different oversampling factors."

    def ami_tst(
        self,
        ami_model: AMIModel, pcfg: AMIParamConfigurator,
        bit_interval: float, sample_interval:float,
        channel_response: Rvec, param_defs: list[TestSweep],
        fig_x: float = 6, fig_y: float = 3,
    ) -> list[Flowable]:
        flowables: list[Flowable] = [
            page_break,
            Paragraph("Samples per Bit", H4),
            Paragraph("Here, we test the model's sensitivity to the oversampling factor, \
                       i.e., number of samples per bit (or, symbol).", P),
            spacer,
        ]
        initializer = pcfg.get_init(
            bit_interval, sample_interval, channel_response, {"root_name": pcfg._root_name})
        flowables.extend(plot_sweeps(samples_per_bit, ami_model, initializer, param_defs,
                                     fig_x=fig_x, fig_y=fig_y))
        flowables.append(
            Paragraph("You should see very little difference between the 3 plots in either chart above.", P))

        return flowables


class AmiTestGetwaveInputLength(AmiTester):
    "Compare ``AMI_GetWave()`` outputs for different input lengths."

    def ami_tst(
        self,
        ami_model: AMIModel, pcfg: AMIParamConfigurator,
        bit_interval: float, sample_interval:float,
        channel_response: Rvec, param_defs: list[TestSweep],
        fig_x: float = 6, fig_y: float = 3,
    ) -> list[Flowable]:
        flowables: list[Flowable] = [
            page_break,
            Paragraph(f"{fixed('AMI_GetWave()')} Input Length Sensitivity", H4),
            Paragraph(f"Sometimes, depending upon how it's implemented, the {fixed('AMI_GetWave()')} function \
                      may exhibit sensitivity to the length of its input. And this is undesireable. \
                      Here, we try to flush that out if it's occurring.", P),
            spacer,
        ]
        if ami_model.has_getwave:
            initializer = pcfg.get_init(
                bit_interval, sample_interval, channel_response, {"root_name": pcfg._root_name})
            flowables.extend(plot_sweeps(check_getwave_input_length, ami_model, initializer, param_defs,
                                         fig_x=fig_x, fig_y=fig_y, finalize=False))
            flowables.append(
                Paragraph("You should see very little difference in either domain \
                          between the various plots in either chart above.", P))
        else:
            flowables.append(Paragraph(f"Model has no {fixed('AMI_GetWave()')} function.", P))

        return flowables


def test_ami_model(
    model: Model,
    ibis_file_dir: Path,
    param_defs: list[TestSweep],
    bit_rate: float,
    nspui: int,
    fig_x: float = 6,
    fig_y: float = 3,
    f_max: float = 40e9,
    f_step: float = 100e6
) -> list[Flowable]:
    """
    Test an individual IBIS-AMI model.

    Args:
        model: The IBIS-AMI model to test.
        ibis_file_dir: Parent directory of ``*.ibs`` file being tested.
        param_defs: List of parameter definition sets to sweep over.
        bit_rate: Bit rate to use for testing.
        nspui: Number of samples per unit interval (a.k.a. - over-sampling factor).

    Keyword Args:
        fix_x: x-dimmension of plot (in.).
            Default: 10
        fix_y: y-dimmension of plot (in.).
            Default: 3
        f_max: Maximum frequency of interest (Hz).
            Default: 40 GHz
        f_step: Frequency increment (Hz).
            Default: 100 MHz

    Returns:
        A list of *ReportLab* ``Flowable``s describing the test results.
    """

    if not model.is_ami:
        return [Paragraph("Error: This model is not an IBIS-AMI model!", P)]

    # Try to fetch AMI files for this machine/system combination.
    machine = platform.machine().lower()
    match(machine):
        case "x86":
            ami_dict = model.ami_files.get('32-bit')
        case "x86_64":
            ami_dict = model.ami_files.get('64-bit')
        case "amd64":
            ami_dict = model.ami_files.get('64-bit')
        case "arm64":
            ami_dict = model.ami_files.get('64-bit')
        case _:
            return [Paragraph(f"Error: Unrecognized machine type: {machine}!", P)]
    system = platform.system().lower()
    match(system):
        case "windows":
            ami_files = ami_dict.get('win')
        case "linux":
            ami_files = ami_dict.get('lin')
        case "darwin":
            ami_files = ami_dict.get('lin')
        case _:
            return [Paragraph(f"Error: Unrecognized system type: {system}!", P)]
    if not ami_files:
        return [Paragraph(f"Error: Model does not provide AMI files for this machine/system combination: {machine}/{system}!", P)]

    flowables: list[Flowable] = [Paragraph("Basic Sanity Checking", H3)]

    # Attempt to create the AMI model and its configurator.
    dll_file, ami_file = list(map(lambda f: ibis_file_dir / Path(f), ami_files))
    try:
        ami_model = AMIModel(str(dll_file))
    except Exception as err:
        return [Paragraph(str(err), P), Paragraph(f"Error loading AMI DLL/SO: {dll_file}!", P)]
    try:
        with open(ami_file, mode="r", encoding="utf-8") as pfile:
            pcfg = AMIParamConfigurator(pfile.read())
        if pcfg.ami_parsing_errors:
            flowables.append(
                Paragraph(preformatted(f"Non-fatal AMI file parsing errors:\n{pcfg.ami_parsing_errors}"),
                          P))
        has_getwave = pcfg.fetch_param_val(["Reserved_Parameters", "GetWave_Exists"]) or False
        ignore_bits = pcfg.fetch_param_val(["Reserved_Parameters", "Ignore_Bits"]) or 0
        returns_impulse = pcfg.fetch_param_val(["Reserved_Parameters", "Init_Returns_Impulse"]) or False
        has_ts4 = True if pcfg.fetch_param_val(["Reserved_Parameters", "Ts4file"]) else False
        root_name = pcfg.input_ami_params[ParamName("root_name")]
    except Exception as err:
        flowables.append(Paragraph(str(err), P))
        flowables.append(Paragraph(f"Error loading AMI parameter file: {ami_file}!", P))
        return flowables

    # Summarize results.
    flowables.append(Paragraph("Model import was successful.", P))
    if has_getwave:
        flowables.append(Paragraph("Model has a `AMI_GetWave()` function.", P))
        flowables.append(Paragraph(f"&nbsp;&nbsp;The first {ignore_bits} returned bits should be ignored.", P))
    else:
        flowables.append(Paragraph("Model has no `AMI_GetWave()` function.", P))
    if returns_impulse:
        flowables.append(Paragraph("Model's `AMI_Init()` function returns an impulse response.", P))
    else:
        flowables.append(Paragraph("Model's `AMI_Init()` function does not return an impulse response.", P))
    if has_ts4:
        flowables.append(Paragraph("Model includes on-die S-parameters.", P))
    else:
        flowables.append(Paragraph("Model does not include on-die S-parameters.", P))

    bit_interval = 1.0 / bit_rate
    sample_interval = bit_interval / nspui

    # Run specific tests.
    testers: Sequence[AmiTester] = [
        AmiTestInitVsGetwave(), AmiTestSamplesPerBit(), AmiTestGetwaveInputLength()]

    def run_testers(channel: Rvec) -> list[Flowable]:
        """
        Run selected model testers, using the given channel response.

        Args:
            channel: Channel impulse resopnse (V/s).

        Returns:
            A list of _ReportLab_ ``Flowable``s comprising the testing results.
        """

        flowables: list[Flowable] = []
        for tester in testers:
            flowables.extend(
                tester.ami_tst(
                    ami_model, pcfg, bit_interval, sample_interval,
                    channel, param_defs, fig_x=fig_x, fig_y=fig_y
                )
            )
        return flowables

    # Test w/ perfect channel.
    flowables.extend([
        Paragraph("Testing w/ Perfect Channel", H3),
        Paragraph("Here, we represent the 'channel' by a Kronecker delta function, \
                  so as to elicit the actual responses of the model itself.", P),
        spacer,
        Paragraph("This imposes certain limitations on our testing. \
                  For instance, since any equalization is over-equalization for such a perfect channel, \
                  if the model imposes:"),
        ListFlowable(
            [Paragraph("a minimum amount of CTLE peaking, or"),
             Paragraph("a minimum first DFE tap value,"),
             Paragraph("etc.,"),
            ], bulletType='bullet', bulletIndent=0.25*inch),
        Paragraph("then we will end up in an over-equalized state."),
        spacer,
        Paragraph("Such a state will not usually affect the AMI_Init() function, \
                  but may affect the AMI_GetWave() function, \
                  particularly if a DFE has been enabled. \
                  And this will cause disagreement between the two. Therefore:"),
        spacer,
        Paragraph("The results of this section should be considered with some skepticism, \
                  as far as inferring how the model will behave in a 'real World' scenario.",
                  bold_style),
        spacer,
        Paragraph(f"The {ital('Lossy Channel')} and {ital('Reflective Channel')} sections, below, \
                  give a more useful assessment of the model's behavior in such real use scenarios."),
    ])

    perfect_channel = np.array(
        [1.0] + [0.0] * (nspui - 1) + [0.0] * 19 * nspui
    ) / sample_interval  # Kronecker delta
    flowables.extend(run_testers(perfect_channel))
    flowables.extend([
        spacer,
        Paragraph(f"{bold('Note:')} If you`ve enabled an adaptive DFE in an Rx model \
                  then the {fixed('AMI_Init()')} and {fixed('AMI_GetWave()')} plots may look different, because:"),
        ListFlowable([
            Paragraph("The channel is perfect here, which means that any equalization \
                      (a minimum amount of CTLE peaking or minimum first DFE tap value, for instance) \
                      is over-equalization, and", P),
            Paragraph(f"The AMI parameter controlling the target voltage at the slicer input \
                      may have a maximum of 1.0V, which is too low in the case of an over-equalized channel. \
                      (The {fixed('AMI_Init()')} function will not be affected by this, \
                      while the {fixed('AMI_GetWave()')} function will.)", P),
        ], bulletFontSize=9, bulletIndent=0.25*inch),
        spacer,
        Paragraph(f"You should see better agreement between the {fixed('AMI_Init()')} and \
                  {fixed('AMI_GetWave()')} outputs, when this test is repeated below for a Lossy channel."),
    ])

    # Test w/ lossy channel.
    flowables.extend([
        page_break,
        Paragraph("Testing w/ Lossy Channel", H3),
        Paragraph("Here, we test the model against a well terminated, but very lossy, channel.", P),
    ])
    b, a = butter(1, bit_rate / 20, fs = 1 / sample_interval)
    lossy_channel = lfilter(
        b, a, np.array([0., 1.] + [0.] * (nspui - 2) + [0.0] * 19 * nspui)
    ) / sample_interval
    flowables.extend(run_testers(lossy_channel))

    # Test w/ reflective channel.
    flowables.extend([
        page_break,
        Paragraph("Testing w/ Reflective Channel", H3),
        Paragraph("Here, we test the model against a poorly terminated, very reflective channel.", P),
    ])
    t = np.arange(20 * nspui) * sample_interval
    f = np.arange(0, f_max + f_step, f_step)
    w = 2 * PI * f
    ts = 0.5 / f_max
    t_fft = np.array([n * ts for n in range(2 * (len(f) - 1))])
    b, a = butter(1, 2 * PI * bit_rate / 2, analog=True)
    _, H = freqs(b, a, worN=w)
    td = 100e-12  # one-way channel delay
    r = 0.2    # reflection coefficient
    H *= (1 - r) * np.exp(-1j * w * td) / (1 - r * np.exp(-2j * w * td))
    h = np.fft.irfft(raised_cosine(H)) / ts
    krnl = interp1d(t_fft, h)
    reflective_channel = krnl(t)
    flowables.extend(run_testers(reflective_channel))

    # Linearity check

    return flowables
