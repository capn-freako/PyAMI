#! /usr/bin/env python

"""
Run IBIS-AMI model(s) through some primitive testing, generating a PDF report.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   March 20, 2026

Copyright (C) 2026 David Banas; all rights reserved World wide.
"""

import click
import traceback

from pathlib  import Path
from typing   import Optional

from reportlab.lib.enums    import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageBreak, PageTemplate,
    Paragraph, Spacer)
from reportlab.platypus.tableofcontents import TableOfContents

from ..util.reportlab   import P, bold, preformatted, title_page

from .ibis_file_tests   import test_ami_models, get_ibis_contents

# Define the PDF document dimensions and grab some pre-defined styles.
PAGE_WIDTH, PAGE_HEIGHT = letter
styles = getSampleStyleSheet()
toc_style = styles['Title']
toc_style.alignment = TA_CENTER
toc_style.fontSize = 16
page_break = PageBreak()
spacer = Spacer(1, 0.25 * inch)

# Define the TOC styles.
toc = TableOfContents()
toc.levelStyles = [
    ParagraphStyle(name='TOCHeading1', fontSize=12, leading=14, leftIndent=0, firstLineIndent=0, spaceBefore=10),
    ParagraphStyle(name='TOCHeading2', fontSize=10, leading=12, leftIndent=10, firstLineIndent=0, spaceBefore=5),
    ParagraphStyle(name='TOCHeading3', fontSize=9, leading=10, leftIndent=15, firstLineIndent=0, spaceBefore=3),
]


# Custom document template.
class MyDocTemplate(BaseDocTemplate):
    def afterFlowable(self, flowable):
        """Called after each flowable is drawn"""
        if isinstance(flowable, Paragraph):
            text = flowable.getPlainText()
            # If the paragraph is a heading, add to TOC
            match flowable.style.name:
                case 'Heading1':
                    key = 'h1-%s' % self.seq.nextf('heading1')
                    self.canv.bookmarkPage(key)
                    self.notify('TOCEntry', (0, text, self.page, key))  # Sends data to the TOC object.
                case 'Heading2':
                    key = 'h2-%s' % self.seq.nextf('heading2')
                    self.canv.bookmarkPage(key)
                    self.notify('TOCEntry', (1, text, self.page))
                case 'Heading3':
                    key = 'h3-%s' % self.seq.nextf('heading3')
                    self.canv.bookmarkPage(key)
                    self.notify('TOCEntry', (2, text, self.page))
                case _:
                    pass


def test_ibis_ami_models(
    ibis_file: Path, test_sweeps_dir: Path,
    model_name: Optional[str] = None,
    max_models_per_file: int = 2,
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
        max_models_per_file: Maximum number of models processed per ``*.ibs`` file.
            Default: 2
        debug: Include debugging output when ``True``.
            Default: ``False``
    """

    ibis_file_dir = ibis_file.parent
    pdf_filename = str((ibis_file_dir / (ibis_file.stem + "_test_results")).with_suffix('.pdf'))

    doc = MyDocTemplate(pdf_filename, pagesize=letter)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
    template = PageTemplate(id='test', frames=frame)
    doc.addPageTemplates([template])
    pages = title_page(ibis_file)

    ibis_model, _ = get_ibis_contents(ibis_file, debug=debug)
    if 'models' not in ibis_model.model_dict or len(ibis_model.model_dict['models']) == 0:
        raise RuntimeError("The IBIS file contains no model definitions!")

    ami_model_names = list(filter(
        lambda nm: ibis_model.model_dict['models'][nm].is_ami,
        ibis_model.model_dict['models'].keys()))
    n_ami_models = len(ami_model_names)
    if n_ami_models == 0:
        raise RuntimeError("There were no AMI models found in this IBIS file.")
    if n_ami_models > max_models_per_file:
        pages.extend([
            spacer,
            Paragraph(preformatted("\n".join([
                f"{bold('Note:')} There were {n_ami_models} AMI models found in this IBIS file.",
                f"Only {max_models_per_file} will be tested.",
            ])), P)
        ])
        ami_model_names = ami_model_names[:max_models_per_file]

    pages.extend([
        page_break,
        Paragraph("Table of Contents", toc_style),
        toc,
    ])

    pages.extend(
        test_ami_models(
            ibis_file, ibis_model, ami_model_names,
            test_sweeps_dir, model_name=model_name, debug=debug)
    )
    doc.multiBuild(pages)


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
    try:
        test_ibis_ami_models(ibis_file_path, test_sweeps_dir, model_name=model, debug=debug)
    except RuntimeError as err:
        error_msg = traceback.format_exception_only(type(err), err)[-1].strip()
        print(error_msg)


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
