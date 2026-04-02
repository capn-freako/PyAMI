"""
Individual tests for AMI models.

Original Author: David Banas <capn.freako@gmail.com>
Original Date:   April 2, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

from reportlab.lib.units import inch
from reportlab.platypus import Flowable, Image, ListFlowable, ListItem, PageBreak, Paragraph, Spacer

from ..common import Rvec, TestSweep
from ..ami.model import AMIModel
from ..ami.parser import AMIParamConfigurator

from .tool_helpers import (
    init_vs_getwave, plot_sweeps, samples_per_bit, check_getwave_input_length,
    bold, ital, fixed, page_break, spacer,
    styles, bold_style, caption_style, indented_style,
    P, H1, H2, H3, H4)


def ami_tst_init_vs_getwave(
    ami_model: AMIModel, pcfg: AMIParamConfigurator,
    bit_interval: float, sample_interval:float,
    channel_response: Rvec, param_defs: list[TestSweep],
    fig_x: float = 6, fig_y: float = 3,
) -> list[Flowable]:
    """
    Compare output from ``AMI_Init()`` and ``AMI_GetWave()`` functions.

    Args:
        ami_model: The AMI model to test.
        pcfg: The AMI model configurator to use/modify.
        bit_interval: The unit interval (s).
        sample_interval: Time between adjacent signal vector elements (s).
        channel_response: Analog channel impulse response (V/sample).
        param_defs: List of AMI/simulation parameter sets to sweep over.

    Keyword Args:
        fig_x: x-dimension of resultant plot figure (in.).
            Default: 6
        fig_y: y-dimension of resultant plot figure (in.).
            Default: 3

    Returns:
        A list of _ReportLab_ ``Flowable``s comprising the results of this test.
    """

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
        spacer,
        Paragraph(f"{bold('Note:')} If you`ve enabled an adaptive DFE in an Rx model \
                  then the plots may look different, because:"),
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

    return flowables
