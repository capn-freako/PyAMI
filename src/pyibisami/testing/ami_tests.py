"""
Individual tests for AMI models.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   April 2, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

import platform

from abc     import ABC, abstractmethod
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing  import Optional, Sequence

from reportlab.lib.units    import inch
from reportlab.platypus     import Flowable, Image, ListFlowable, Paragraph

from ..ami.model        import AMIModel, OUT_RESP_INIT
from ..ami.parser       import AMIParamConfigurator
from ..ibis.model       import Model
from ..util.plot        import plt
from ..util.reportlab   import (
    bold, fixed, page_break, spacer, preformatted,
    P, H3, H4, H5)

from .ami_tests_helpers import (
    AmiTestHelper, AmiTestHelperInitVsGetwave,
    AmiTestHelperSamplesPerBit, AmiTestHelperGetwaveInputLength, 
    plot_sweep)
from .test_defs import TestSweep

FIG_X_DFLT = 6.0
FIG_Y_DFLT = 4.0
DEBUG = False


class AmiTester(ABC):
    "Abstract class defining the structure and default behavior of an IBIS-AMI model tester."

    @property
    def helper(self) -> AmiTestHelper:
        "Each subclass must define a test helper."
        raise NotImplementedError()

    preamble: list[Flowable] = []  # Any desired introductory text for report body.

    def ami_tst(
        self,
        ami_model: AMIModel, pcfg: AMIParamConfigurator,
        test_sweepers: list[tuple[Optional[str], list[type[TestSweep]]]],
        fig_x: float = FIG_X_DFLT, fig_y: float = FIG_Y_DFLT,
    ) -> list[Flowable]:
        """
        Perform some test on an ``AMIModel`` instance,
        using several different parameter sweep groups.

        Args:
            ami_model: The AMI model to test.
            pcfg: The AMI model configurator to use/modify.
            test_sweepers: List of AMI/simulation parameter set groups to sweep over.

        Keyword Args:
            fig_x: x-dimension of resultant plot figure (in.).
                Default: ``FIG_X_DFLT``
            fig_y: y-dimension of resultant plot figure (in.).
                Default: ``FIG_Y_DFLT``

        Returns:
            A list of _ReportLab_ ``Flowable``s comprising the results of this test.
        """

        flowables: list[Flowable] = self.preamble
        for mod_doc, test_sweeps in test_sweepers:
            _mod_doc: str = mod_doc or "(No module description)"
            p = Paragraph(_mod_doc, H4)
            p.keepWithNext = True
            flowables.append(p)
            for test_sweep in test_sweeps:
                sweep_desc: str = test_sweep.__doc__ if test_sweep.__doc__ else "(No class description)"
                p = Paragraph(sweep_desc, H5)
                p.keepWithNext = True
                flowables.append(p)
                flowables.extend(plot_sweep(
                    self.helper, ami_model, pcfg, test_sweep,
                    fig_x=fig_x, fig_y=fig_y))
        return flowables


class AmiTestLinearityChecker(AmiTester):
    "Check ``AMI_Init()`` for linearity."

    preamble = [
        page_break,
        Paragraph(f"{fixed('AMI_Init()')} Linearity Check", H3),
        Paragraph(f"Here, we check that the {fixed('AMI_Init()')} function is linear."),
        spacer,
        Paragraph(
            f"{bold('Note:')} There is no requirement that the {fixed('AMI_GetWave()')} \
            function exhibit linearity. In fact, the {fixed('AMI_GetWave()')} function is \
            often used to capture non-linear behavior.", P),
        spacer,
        Paragraph(f"Compare each pair of red and blue traces below. \
                  If the model's {fixed('AMI_Init()')} function is truly linear, \
                  then the two should look identical.", P),
    ]

    def ami_tst(
        self, ami_model, pcfg, test_sweepers,
        fig_x = 5, fig_y = 3,
    ) -> list[Flowable]:
        flowables: list[Flowable] = self.preamble
        for mod_doc, test_sweeps in test_sweepers:
            _mod_doc: str = mod_doc or "(No module description)"
            p = Paragraph(_mod_doc, H4)
            p.keepWithNext = True
            flowables.append(p)
            for test_sweep in test_sweeps:
                sweep_desc: str = test_sweep.__doc__ if test_sweep.__doc__ else "(No class description)"
                p = Paragraph(sweep_desc, H5)
                p.keepWithNext = True
                flowables.append(p)
                for test_def in test_sweep().test_sweep():
                    p = Paragraph(preformatted(f"\t{test_def.description}:"), P)
                    p.keepWithNext = True
                    flowables.append(p)
                    # Test model against full channel response.
                    initializer = pcfg.get_init(
                        test_def.sim_params["bit_time"],
                        test_def.sim_params["sample_interval"],
                        test_def.sim_params["channel_response"],
                        test_def.ami_params
                    )
                    ami_model.initialize(initializer)
                    model_resps = ami_model.get_responses(nbits=test_def.sim_params["nbits"])
                    t, _, _, resp_to_sum, _, _ = model_resps[OUT_RESP_INIT]
                    fig = plt.figure(figsize=(fig_x, fig_y))
                    plt.plot(t * 1e9, resp_to_sum, label="Response to Sum")
                    # Test model against half channel response.
                    initializer.channel_response = [x / 2 for x in initializer.channel_response]
                    ami_model.initialize(initializer)
                    model_resps = ami_model.get_responses(nbits=test_def.sim_params["nbits"])
                    t, _, _, sum_of_resps, _, _ = model_resps[OUT_RESP_INIT]
                    sum_of_resps *= 2
                    plt.plot(t * 1e9, sum_of_resps, label="Sum of Responses")
                    plt.title("Comparing Pulse Responses")
                    plt.xlabel("Time (ns)")
                    plt.ylabel("p(t) (V)")
                    plt.legend()
                    with NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                        plt.savefig(tmp_file)
                        flowables.append(Image(tmp_file.name, width=fig_x*inch, height=fig_y*inch))
                    plt.close()
                flowables.append(spacer)

        return flowables


class AmiTestInitVsGetwave(AmiTester):
    "Compare output from ``AMI_Init()`` and ``AMI_GetWave()`` functions."

    helper = AmiTestHelperInitVsGetwave(DEBUG)

    preamble = [
        Paragraph("Init() vs. GetWave()", H3),
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
        Paragraph(f"{bold('Plot notes:')}", P),
        ListFlowable([
            Paragraph(f"Solid lines are {fixed('Init()')}; dashed are {fixed('GetWave()')}."),
            Paragraph("Step response shown at reduced brightness."),
        ], bulletFontSize=9),
        spacer,
        Paragraph(f"Compare the plots below. \
                  The {fixed('Init()')} (solid) and {fixed('GetWave()')} (dashed) plots \
                  should look nearly identical.", P),
        Paragraph(f"({bold('Note:')} Ignore the waveform before time zero; \
                  it`s not expected to match and is plotted only as a debugging aid.)", P),
        spacer,
    ]


class AmiTestSamplesPerBit(AmiTester):
    "Compare model response at different oversampling factors."

    helper = AmiTestHelperSamplesPerBit()

    preamble = [
        page_break,
        Paragraph("Samples per Bit", H3),
        Paragraph("Here, we test the model's sensitivity to the oversampling factor, \
                   i.e., number of samples per bit (or, symbol).", P),
        Paragraph("You should see very little difference between the 3 plots in any of the charts below.", P),
        spacer,
    ]


class AmiTestGetwaveInputLength(AmiTester):
    "Compare ``AMI_GetWave()`` outputs for different input lengths."

    helper = AmiTestHelperGetwaveInputLength()

    def ami_tst(
        self, ami_model, pcfg, test_sweepers,
        fig_x = 6, fig_y = 2,
    ) -> list[Flowable]:
        preamble: list[Flowable] = [
            page_break,
            Paragraph(f"{fixed('AMI_GetWave()')} Input Length Sensitivity", H3),
            Paragraph(f"Sometimes, depending upon how it's implemented, the {fixed('AMI_GetWave()')} function \
                      may exhibit sensitivity to the length of its input. And this is undesireable. \
                      Here, we try to flush that out if it's occurring.", P),
            spacer,
        ]
        if ami_model.has_getwave:
            preamble.append(
                Paragraph("You should see very little difference, in either domain, \
                          between the various plots in any of the charts below.", P)
            )
            self.preamble = preamble
            return super().ami_tst(ami_model, pcfg, test_sweepers, fig_x=fig_x, fig_y=fig_y)
        else:
            preamble.append(
                Paragraph(f"Model has no {fixed('AMI_GetWave()')} function.", P)
            )
            return preamble


def test_ami_model(
    model: Model, ibis_file_dir: Path,
    test_sweepers: list[tuple[Optional[str], list[type[TestSweep]]]],
    f_max: float = 40e9, f_step: float = 10e6
) -> list[Flowable]:
    """
    Test an individual IBIS-AMI model.

    Args:
        model: The IBIS-AMI model to test.
        ibis_file_dir: Parent directory of ``*.ibs`` file being tested.
        test_sweepers: List of parameter definition set groups to sweep over.

    Keyword Args:
        f_max: Maximum frequency of interest (Hz).
            Default: 40 GHz
        f_step: Frequency increment (Hz).
            Default: 10 MHz

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

    # Run specific tests.
    testers: Sequence[AmiTester] = [
        AmiTestInitVsGetwave(),
        AmiTestSamplesPerBit(),
        AmiTestGetwaveInputLength(),
        AmiTestLinearityChecker(),
    ]

    for tester in testers:
        flowables.extend(
            tester.ami_tst(ami_model, pcfg, test_sweepers))

    return flowables
