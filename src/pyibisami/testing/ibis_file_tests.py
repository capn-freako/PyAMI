"""
Testing of whole IBIS (``*.ibs``) _files_.

Original author: David Banas <capn.freako@gmail.com>

Original date: April 3, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

import subprocess

from pathlib import Path
from typing import Optional

from reportlab.platypus import Flowable, Image, ListFlowable, ListItem, PageBreak, Paragraph, Spacer

from ..common import TestSweep
from ..ibis.file import IBISModel
from ..util.reportlab_combinators import preformatted
from ..util.tool_helpers import (
    init_vs_getwave, plot_sweeps, samples_per_bit, check_getwave_input_length,
    bold, ital, fixed, page_break, spacer,
    styles, bold_style, caption_style, indented_style,
    P, H1, H2, H3, H4)

from .ami_tests import test_ami_model

IBIS_CHK_EXEC = "ibischk7_64"


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

    flowables: list[Flowable] = [Paragraph("IBIS File Contents", H1)]

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

    flowables: list[Flowable] = [Paragraph("IBIS Golden Parser Results", H1)]
    result = subprocess.run([IBIS_CHK_EXEC, str(ibis_file)], capture_output=True, text=True)
    flowables.append(Paragraph(preformatted(result.stdout), styles['Code']))
    flowables.append(Paragraph(preformatted(result.stderr), styles['Code']))
    flowables.append(page_break)
    return flowables


def test_ami_models(
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

    flowables: list[Flowable] = [Paragraph("IBIS-AMI Model(s) Testing Results", H1)]

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
        flowables.append(Paragraph(f"Testing Model: {model_name}", H2))
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
