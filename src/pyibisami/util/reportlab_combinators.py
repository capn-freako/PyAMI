"""
Utilities for generating certain commonly occurring combinations of *ReportLab* ``Flowable``s.

Original Author: David Banas <capn.freako@gmail.com>
Original Date:   March 21, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

import platform
import sys

from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import scipy as sp

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Flowable, Image, ListFlowable, ListItem, PageBreak, Paragraph, Spacer

from ..common import TestSweep
from ..ami.model import AMIModel
from ..ami.parser import AMIParamConfigurator, ParamName
from ..ibis.file import IBISModel
from ..ibis.model import Model
# from ..testing.ami_tests import ami_tst_init_vs_getwave, ami_tst_samples_per_bit, ami_tst_getwave_input_length
# from ..testing.ibis_file_tests import get_ibis_contents, golden_parser_results

from .tool_helpers import (
    init_vs_getwave, plot_sweeps, samples_per_bit, check_getwave_input_length,
    bold, ital, fixed, page_break, spacer,
    styles, bold_style, caption_style, indented_style,
    P, H1, H2, H3, H4)

# General formatting utilities
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
    flowables.append(Paragraph(f"{bold('Date:')} {datetime.now()}", P))
    flowables.append(Paragraph(f"{bold('Tested:')} {ibis_file}", P))
    flowables.append(Paragraph(f"{bold('Python:')} {sys.version}", P))
    flowables.append(Paragraph(f"{bold('NumPy:')} {np.__version__}", P))
    flowables.append(Paragraph(f"{bold('SciPy:')} {sp.__version__}", P))
    flowables.append(page_break)
    return flowables
