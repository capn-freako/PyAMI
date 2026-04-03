"""
Common helper utilities used by the various scripts in ``testing/``.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   March 20, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

import sys

from datetime   import datetime
from pathlib    import Path
from random     import randrange
from tempfile   import NamedTemporaryFile
from typing     import Any, Callable, Generator, NewType

import numpy as np
import scipy as sp

from matplotlib             import pyplot as plt
from matplotlib.figure      import Figure
from reportlab.lib.enums    import TA_CENTER
from reportlab.lib.styles   import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units    import inch
from reportlab.platypus     import Flowable, Image, PageBreak, Paragraph, Spacer

from ..common       import Rvec, TestSweep
from ..ami.model    import AMIModel, AMIModelInitializer

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


# HTML formatters
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
    return tag("code", text)


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


# Common `Flowable` lists.
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
