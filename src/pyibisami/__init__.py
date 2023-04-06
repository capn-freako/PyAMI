"""A package of Python modules, used to configure and test IBIS-AMI models.

.. moduleauthor:: David Banas <capn.freako@gmail.com>

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   3 July 2012

Copyright (c) 2012 by David Banas; All rights reserved World wide.
"""
from importlib.metadata import version as _get_version

# Set PEP396 version attribute
__version__ = _get_version('PyIBIS-AMI')  # PyPi "PyBERT" package name got stollen. :(
__date__ = "April 6, 2023"
__authors__ = "David Banas & David Patterson"
__copy__ = "Copyright (c) 2012 David Banas, 2019 David Patterson"
