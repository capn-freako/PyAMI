"""
Testing infrastructure for IBIS-AMI models.

Original author: David Banas <capn.freako@gmail.com>

Original date: April 3, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.

**Note:** This testing infrastructure relies on the _ReportLab_ package
and is intended to produce a final model testing report in PDF format.

**Note:** Unlike previous model testing mechanisms included in the _PyIBIS-AMI_ package,
this new testing infrastructure makes no use of either:

- _Jupyter_ notebooks, or
- _EmPy_ templating schemes.

This change was made, in order to make the testing infrastructure both:

- more performant, and
- easier to debug.
"""
