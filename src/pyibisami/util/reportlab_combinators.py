"""
Utilities for generating certain commonly occurring combinations of *ReportLab* ``Flowable``s.

Original Author: David Banas <capn.freako@gmail.com>
Original Date:   March 21, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

import sys

from datetime import datetime
from pathlib import Path

import numpy as np
import scipy as sp

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Flowable, PageBreak, Paragraph, Spacer

from ..ibis.file import IBISModel

styles = getSampleStyleSheet()
page_break = PageBreak()


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
    flowables.append(
        Paragraph(ibis_model.info().replace('\n', '<br />').replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;'),
                  styles['Code']))
    flowables.append(page_break)

    return (ibis_model, flowables)
