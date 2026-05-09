#! /usr/bin/env python

"""
Run IBIS-AMI model(s) through some primitive testing, generating a PDF report.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   March 20, 2026

Copyright (C) 2026 David Banas; all rights reserved World wide.
"""

import click
import inspect
import types

from pathlib  import Path
from typing   import Optional

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

import pyibisami

from ..util.misc        import import_from_path
from ..util.reportlab   import title_page

from .ibis_file_tests   import test_ami_models, get_ibis_contents, golden_parser_results
from .test_defs         import TestSweep

# Define the PDF document dimensions and grab some pre-defined styles.
PAGE_WIDTH, PAGE_HEIGHT = letter
styles = getSampleStyleSheet()
page_break = PageBreak()
title_style = styles['Title']
title_style.alignment = TA_LEFT
spacer = Spacer(1, 0.25*inch)


def test_ibis_ami_models(
    ibis_file: Path, test_sweeps_dir: Path, 
    model_name: Optional[str] = None,
    debug: bool = False
) -> None:
    """
    Test some subset of the IBIS-AMI models in a ``*.ibs`` file.

    Args:
        ibis_file: The ``*.ibs`` file to test.
        test_sweeps_dir: Test parameter sweep definitions.

    Keyword Args:
        model_name: The particular model to test.
            Default: None (Means test all IBIS-AMI models found in ``*.ibs`` file.)
        debug: Include debugging output when ``True``.
            Default: ``False``
    """

    ibis_file_dir = ibis_file.parent
    pdf_filename = str((ibis_file_dir / (ibis_file.stem + "_test_results")).with_suffix('.pdf'))
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

    doc = SimpleDocTemplate(pdf_filename)

    # title page
    pages = title_page(ibis_file)

    # Fetch/print IBIS file contents.
    # ibis_model, flowables = get_ibis_contents(ibis_file, debug=debug)
    # pages.extend(flowables)

    # golden parser results
    # pages.extend(golden_parser_results(ibis_file))
    pages.extend([
        spacer,
        Paragraph(
            preformatted("\n".join([
                f"{bold("Note:")} You should always run any new IBIS(-AMI) model through the {ital("Golden Parser")}.",
                f"You can find more information about how to do this at the {ital("Open IBIS Forum")}'s web site:",
                "https://www.ibis.org/ibischk7/",
                ])),
            P)
        ])

    pages.extend(
        test_ami_models(
            ibis_file, ibis_model, test_sweeps_dir,
            model_name=model_name, debug=debug)
    )
    doc.build(pages, onFirstPage=myFirstPage, onLaterPages=myLaterPages)


# CLI definition
@click.command(context_settings={"ignore_unknown_options": False,
                                 "help_option_names": ["-h", "--help"]})
@click.option("--model",  "-m", type=str,
    help="Name of IBIS-AMI model to test.")
@click.option("--params", "-p", type=str, default='test_runs',
    help='Directory containing test configuration sweeps.',
)
@click.option("--debug", "-d", is_flag=True, help="Provide extra debugging information.")
@click.argument("ibis_file", type=click.Path(exists=True))
@click.version_option(package_name="PyIBIS-AMI")
def main(ibis_file, model, params, debug):
    ibis_file_path = Path(ibis_file).resolve()
    if not ibis_file_path.exists():
        raise RuntimeError(f"IBIS file `{ibis_file_path}` does not exist!")
    test_sweeps_dir = Path(params).resolve()
    test_sweeps_dir.mkdir(parents=True, exist_ok=True)
    test_ibis_ami_models(ibis_file_path, test_sweeps_dir, model_name=model, debug=debug)


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
