"""
Miscellaneous utilities.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   May 4, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

import importlib.util

def import_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    # sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
