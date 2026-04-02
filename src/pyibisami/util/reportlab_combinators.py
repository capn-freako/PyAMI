"""
Utilities for generating certain commonly occurring combinations of *ReportLab* ``Flowable``s.

Original Author: David Banas <capn.freako@gmail.com>
Original Date:   March 21, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

import platform
import subprocess
import sys

from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import scipy as sp

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Flowable, Image, PageBreak, Paragraph, Spacer

from ..common import TestSweep
from ..ami.model import AMIModel
from ..ami.parser import AMIParamConfigurator, ParamName
from ..ibis.file import IBISModel
from ..ibis.model import Model

from .tool_helpers import init_vs_getwave, plot_sweeps

styles = getSampleStyleSheet()
page_break = PageBreak()
spacer = Spacer(inch, 0.2*inch)

def preformatted(text: str) -> str:
    """
    Convert ``\n`` and ``\t`` characters in a pre-formatted string
    for display in a *ReportLab* ``Paragraph``.
    
    Args:
        text: The pre-formatted text containing ``\n`` and ``\t`` characters to convert.

    Returns:
        The converted string.
    """

    return text.replace('\n', '<br />').replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;')


def title_page(ibis_file: Path) -> list[Flowable]:
    """
    Generate the list of *ReportLab* ``Flowable``s needed for the report title page.

    Args:
        ibis_file: The file path of the IBIS model being tested.

    Returns:
        A list of *ReportLab* ``Flowable``s providing report title page information.
    """

    flowables: list[Flowable] = [Spacer(1, 3*inch)]
    flowables.append(Paragraph(f"<strong>Date:</strong> {datetime.now()}", styles['Normal']))
    flowables.append(Paragraph(f"<strong>Tested:</strong> {ibis_file}", styles['Normal']))
    flowables.append(Paragraph(f"<strong>Python:</strong> {sys.version}", styles['Normal']))
    flowables.append(Paragraph(f"<strong>NumPy:</strong> {np.__version__}", styles['Normal']))
    flowables.append(Paragraph(f"<strong>SciPy:</strong> {sp.__version__}", styles['Normal']))
    flowables.append(page_break)
    return flowables


def get_ibis_contents(ibis_file: Path) -> tuple[IBISModel, list[Flowable]]:
    """
    List the components and models available in an IBIS model file.

    Args:
        ibis_file: The IBIS model file to be interrogated.

    Returns:
        A pair containing

        - the ``IBISModel`` object, and
        - the list of *ReportLab* ``Flowable``s describing the model contents.
    """

    flowables: list[Flowable] = [Paragraph("IBIS File Contents", styles['Heading1'])]

    # Attempt to parse `*.ibs` file.
    try:
        ibis_model = IBISModel(str(ibis_file), False, gui=False)
    except Exception as err:
        raise RuntimeError(f"An error occurred while trying to read/parse the IBIS model file: {ibis_file}") from err

    # Build the list of ReportLab Flowable elements for the IBIS model contents page of the report.
    flowables.append(Paragraph(preformatted(ibis_model.info()), styles['Code']))
    flowables.append(page_break)

    return (ibis_model, flowables)


def golden_parser_results(ibis_file: Path) -> list[Flowable]:
    """
    Run the ``ibischk`` parser on the IBIS file and return the results.

    Args:
        ibis_file: The IBIS model file to be interrogated.

    Returns:
        The list of *ReportLab* ``Flowable``s describing the parsing results.
    """

    flowables: list[Flowable] = [Paragraph("IBIS Golden Parser Results", styles['Heading1'])]
    result = subprocess.run(['ibischk7_64', str(ibis_file)], capture_output=True, text=True)
    flowables.append(Paragraph(preformatted(result.stdout), styles['Code']))
    flowables.append(Paragraph(preformatted(result.stderr), styles['Code']))
    flowables.append(page_break)
    return flowables


def test_ami_model(
    model: Model,
    ibis_file_dir: Path,
    param_defs: list[TestSweep],
    bit_rate: float,
    nspui: int,
    fig_x: float = 6,
    fig_y: float = 2,
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

    Returns:
        A list of *ReportLab* ``Flowable``s describing the test results.
    """

    if not model.is_ami:
        return [Paragraph("Error: This model is not an IBIS-AMI model!", styles['Normal'])]

    # Perform basic sanity checking and reporting.
    machine = platform.machine().lower()
    system = platform.system().lower()
    match(machine):
        case "x86":
            ami_dict = model.ami_files['32-bit']
            match(system):
                case "windows":
                    ami_files = ami_dict['win']
                case "linux":
                    ami_files = ami_dict['lin']
                case "darwin":
                    ami_files = ami_dict['lin']
                case _:
                    return [Paragraph(f"Error: Unrecognized system type: {system}!", styles['Normal'])]
        case "x86_64":
            ami_dict = model.ami_files['64-bit']
            match(system):
                case "windows":
                    ami_files = ami_dict['win']
                case "linux":
                    ami_files = ami_dict['lin']
                case "darwin":
                    ami_files = ami_dict['lin']
                case _:
                    return [Paragraph(f"Error: Unrecognized system type: {system}!", styles['Normal'])]
        case "amd64":
            ami_dict = model.ami_files['64-bit']
            match(system):
                case "windows":
                    ami_files = ami_dict['win']
                case "linux":
                    ami_files = ami_dict['lin']
                case "darwin":
                    ami_files = ami_dict['lin']
                case _:
                    return [Paragraph(f"Error: Unrecognized system type: {system}!", styles['Normal'])]
        case "arm64":
            ami_dict = model.ami_files['64-bit']
            match(system):
                case "windows":
                    ami_files = ami_dict['win']
                case "linux":
                    ami_files = ami_dict['lin']
                case "darwin":
                    ami_files = ami_dict['lin']
                case _:
                    return [Paragraph(f"Error: Unrecognized system type: {system}!", styles['Normal'])]
        case _:
            return [Paragraph(f"Error: Unrecognized machine type: {machine}!", styles['Normal'])]
    if not ami_files:
        return [Paragraph(f"Error: Model does not provide AMI files for this machine/system combination: {machine}/{system}!", styles['Normal'])]

    flowables: list[Flowable] = [Paragraph("Basic Sanity Checking", styles['Heading3'])]

    # Attempt to create the AMI model and its configurator.
    dll_file, ami_file = list(map(lambda f: ibis_file_dir / Path(f), ami_files))
    try:
        ami_model = AMIModel(str(dll_file))
    except Exception as err:
        return [Paragraph(str(err), styles['Normal']), Paragraph(f"Error loading AMI DLL/SO: {dll_file}!", styles['Normal'])]
    try:
        with open(ami_file, mode="r", encoding="utf-8") as pfile:
            pcfg = AMIParamConfigurator(pfile.read())
        if pcfg.ami_parsing_errors:
            flowables.append(
                Paragraph(preformatted(f"Non-fatal AMI file parsing errors:\n{pcfg.ami_parsing_errors}"),
                          styles['Normal']))
        has_getwave = pcfg.fetch_param_val(["Reserved_Parameters", "GetWave_Exists"]) or False
        ignore_bits = pcfg.fetch_param_val(["Reserved_Parameters", "Ignore_Bits"]) or 0
        returns_impulse = pcfg.fetch_param_val(["Reserved_Parameters", "Init_Returns_Impulse"]) or False
        has_ts4 = True if pcfg.fetch_param_val(["Reserved_Parameters", "Ts4file"]) else False
        root_name = pcfg.input_ami_params[ParamName("root_name")]
    except Exception as err:
        flowables.append(Paragraph(str(err), styles['Normal']))
        flowables.append(Paragraph(f"Error loading AMI parameter file: {ami_file}!", styles['Normal']))
        return flowables

    # Summarize results.
    flowables.append(Paragraph("Model import was successful.", styles['Normal']))
    if has_getwave:
        flowables.append(Paragraph("Model has a `AMI_GetWave()` function.", styles['Normal']))
        flowables.append(Paragraph(f"&nbsp;&nbsp;The first {ignore_bits} returned bits should be ignored.", styles['Normal']))
    else:
        flowables.append(Paragraph("Model has no `AMI_GetWave()` function.", styles['Normal']))
    if returns_impulse:
        flowables.append(Paragraph("Model's `AMI_Init()` function returns an impulse response.", styles['Normal']))
    else:
        flowables.append(Paragraph("Model's `AMI_Init()` function does not return an impulse response.", styles['Normal']))
    if has_ts4:
        flowables.append(Paragraph("Model includes on-die S-parameters.", styles['Normal']))
    else:
        flowables.append(Paragraph("Model does not include on-die S-parameters.", styles['Normal']))

    # Test w/ perfect channel.
    flowables.append(Paragraph("Testing w/ Perfect Channel", styles['Heading3']))
    bit_interval = 1.0 / bit_rate
    sample_interval = bit_interval / nspui
    channel_response = np.array([1.0] + [0.0] * (nspui - 1) + [0.0] * 19 * nspui) / sample_interval  # Kronecker delta

    # - Init() vs. GetWave()
    initializer = pcfg.get_init(
        bit_interval, sample_interval, channel_response, {"root_name": pcfg._root_name})
    flowables.extend(plot_sweeps(init_vs_getwave, ami_model, initializer, param_defs,
                                 fig_x=fig_x, fig_y=fig_y))

    # - samples per bit
    # - linearity check
    # - GetWave() input length sensitivity

    # Test w/ lossy channel.

    # Test w/ reflective channel.

    return flowables


def model_test_results(
    ibis_file_dir: Path, ibis_model: IBISModel,
    bit_rate: float, nspui: int,
    param_defs: list[TestSweep],
    model_name: Optional[str] = None,
    debug: bool=False
) -> list[Flowable]:
    """
    Test a subset of the IBIS-AMI models in the ``*.ibs`` file.

    Args:
        ibis_file_dir: The parent directory of the ``*.ibs`` file being tested.
        ibis_model: The read and parsed ``*.ibs`` file.
        bit_rate: The desired bit rate for testing.
        nspui: Number of samples per unit interval (a.k.a. - over-sampling factor).
        param_defs: The list of parameter sweep definitions to use for this test.

    Keyword Args:
        model_name: The name of a particular model to test.
            Default = ``None`` (Means test all IBIS-AMI models found.)
        debug: Include extra debugging output when ``True``.
            Default = ``False``

    Returns:
        The list of *ReportLab* ``Flowable``s describing the testing results.
    """

    flowables: list[Flowable] = [Paragraph("IBIS-AMI Model(s) Testing Results", styles['Heading1'])]

    if 'models' not in ibis_model.model_dict:
        flowables.append(Paragraph("Error: The parsed IBIS file contained no model definitions!"))
        flowables.append(page_break)
        return flowables

    def do_model(model_name: str) -> list[Flowable]:
        """
        Generate the output for one model.

        Args:
            model_name: Name of model to test.

        Returns:
            List of _ReportLab_ ``Flowable``s describing the model testing results.
        """
        flowables.append(Paragraph(f"Testing Model: {model_name}", styles['Heading2']))
        model = ibis_model.model_dict['models'][model_name]
        flowables.append(Paragraph(preformatted(f"{model}"), styles['Code']))
        flowables.extend(test_ami_model(model, ibis_file_dir, param_defs, bit_rate, nspui))
        flowables.append(page_break)
        return flowables

    if model_name:
        if model_name not in ibis_model.model_dict['models']:
            flowables.append(Paragraph(f"Error: The requested model: {model_name}, was not found!"))
            flowables.append(page_break)
            return flowables
        do_model(model_name)
        return flowables

    for model_name in ibis_model.model_dict['models']:
        do_model(model_name)

    return flowables
