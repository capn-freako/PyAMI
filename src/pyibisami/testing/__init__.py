"""
Testing infrastructure for IBIS-AMI models.

Original author: David Banas <capn.freako@gmail.com>

Original date: April 3, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.

**Note:** This package holds the test definitions and the IBIS 8.0 ``[AMI Test Configuration]`` runner,
which need only the core dependencies.
The final model testing report, in PDF format, is produced by ``pyibisami.report``,
which requires the ``report`` extra (_ReportLab_ & _Matplotlib_).

**Note:** Unlike previous model testing mechanisms included in the _PyIBIS-AMI_ package,
this new testing infrastructure makes no use of either:

- _Jupyter_ notebooks, or
- _EmPy_ templating schemes.

This change was made, in order to make the testing infrastructure both:

- more performant, and
- easier to debug.
"""
