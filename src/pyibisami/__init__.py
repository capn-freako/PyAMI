"""A package of Python modules, used to configure and test IBIS-AMI models.

.. moduleauthor:: David Banas <capn.freako@gmail.com>

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   3 July 2012

Copyright (c) 2012 by David Banas; All rights reserved World wide.
"""

from importlib.metadata import version as _get_version

# Set PEP396 version attribute
try:
    __version__ = _get_version("PyIBIS-AMI")
except Exception as err:  # pylint: disable=broad-exception-caught
    __version__ = f"{err} (dev)"

__date__ = "October 12, 2023"
__authors__ = "David Banas & David Patterson"
__copy__ = "Copyright (c) 2012 David Banas, 2019 David Patterson"
