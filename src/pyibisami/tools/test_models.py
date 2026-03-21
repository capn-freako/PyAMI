#! /usr/bin/env python

"""
Run IBIS-AMI model(s) through some primitive testing, generating a PDF report.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   March 20, 2026

Copyright (pdf) 2026 David Banas; all rights reserved World wide.
"""

import click
import sys

import numpy as np
import scipy as sp

from datetime import datetime
from pathlib  import Path
from typing   import Optional

from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Flowable, Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table

import pyibisami
from ..util.reportlab_combinators import get_ibis_contents, title_page

# Define the PDF document dimensions and grab some pre-defined styles.
PAGE_WIDTH, PAGE_HEIGHT = letter
styles = getSampleStyleSheet()
page_break = PageBreak()
title_style = styles['Title']
title_style.alignment = TA_LEFT
spacer = Spacer(1, 0.25*inch)


def test_ibis_ami_models(
    ibis_file: Path, bit_rate: float, model: Optional[str] = None,
    debug: bool = False
) -> None:
    """
    Test some subset of the IBIS-AMI models in a ``*.ibs`` file.

    Args:
        ibis_file: The ``*.ibs`` file to test.
        bit_rate: The bit rate to use for testing.

    Keyword Args:
        model: Name of model to test.
            Default = ``None`` (Means test all IBIS-AMI models found.)
        debug: Include debugging output when ``True``.
            Default = ``False``
    """

    pdf_filename = str((ibis_file.parent / (ibis_file.stem + "_test_results")).with_suffix('.pdf'))
    title = Paragraph(f"<em>PyIBIS-AMI</em> v{pyibisami.__version__} - IBIS-AMI Model Testing Report", title_style)
    pageinfo = f"Model Testing Report for: {ibis_file}"

    def myFirstPage(canvas, doc):
        canvas.saveState()
        title.wrapOn(canvas, PAGE_WIDTH, PAGE_HEIGHT)
        title.drawOn(canvas, 1*inch, 9*inch)
        canvas.restoreState()

    def myLaterPages(canvas, doc):
        canvas.saveState()
        canvas.setFont('Times-Roman',9)
        canvas.drawString(inch, 0.75 * inch, "Page %d - %s" % (doc.page, pageinfo))
        canvas.restoreState()

    # Add the flowables to the canvas
    def go():
        doc = SimpleDocTemplate(pdf_filename)

        # title page
        pages = title_page(ibis_file)

        # Fetch/print IBIS file contents.
        model, flowables = get_ibis_contents(ibis_file)
        pages.extend(flowables)

        # golden parser results
        pages.append(Paragraph("IBIS Golden Parser Results", styles['Heading1']))
        pages.append(page_break)

        # pages.append(image)
        # pages.append(spacer)
        # pages.append(table)

        doc.build(pages, onFirstPage=myFirstPage, onLaterPages=myLaterPages)

    go()


# CLI definition
@click.command(context_settings={"ignore_unknown_options": False,
                                 "help_option_names": ["-h", "--help"]})
@click.option("--debug", is_flag=True, help="Provide extra debugging information.")
@click.option("--model", type=str, default=None, help="Limit testing to just the named model.")
@click.argument("ibis_file", type=click.Path(exists=True))
@click.argument("bit_rate", type=float)
@click.version_option(package_name="PyIBIS-AMI")
def main(ibis_file, bit_rate, model, debug):
    ibis_file_path = Path(ibis_file, exists=True).resolve()
    test_ibis_ami_models(ibis_file_path, bit_rate, debug=debug, model=model)


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter


    # file_id.wrapOn(pdf, PAGE_WIDTH, PAGE_HEIGHT)
    # file_id.drawOn(pdf, 1*inch, 9*inch)

    # spacer.wrapOn(pdf, PAGE_WIDTH, PAGE_HEIGHT)
    # spacer.drawOn(pdf, 1*inch, 8.5*inch)

    # pdf.showPage()  # Inserts a page break.

    # image.wrapOn(pdf, PAGE_WIDTH, PAGE_HEIGHT)
    # image.drawOn(pdf, 1*inch, 6*inch)

    # table.wrapOn(pdf, PAGE_WIDTH, PAGE_HEIGHT)
    # table.drawOn(pdf, 1*inch, 3*inch)

    # Save the PDF document
    # pdf.save()

    # Create an image flowable
    # image = Image('./htmlcov/favicon_32_cb_58284776.png', width=2*inch, height=2*inch)

    # Create a table flowable
    # data = [
    #     ['Name', 'Age', 'Country'],
    #     ['Alice', '25', 'USA'],
    #     ['Bob', '30', 'Canada'],
    #     ['Charlie', '40', 'Australia'],
    # ]
    # table = Table(data)


