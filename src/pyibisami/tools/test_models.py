#! /usr/bin/env python

"""
Run IBIS-AMI model(s) through some primitive testing, generating a PDF report.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   March 20, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

from reportlab.pdfgen import canvas


def test_ibis_ami_models():
    """
    Test some subset of the IBIS-AMI models in a ``*.ibs`` file.
    """

    # Create a new PDF document
    pdf = canvas.Canvas('example.pdf')

    # Add some text to the document
    pdf.drawString(100, 750, "Welcome to ReportLab!")

    # Save the PDF document
    pdf.save()
