"""
General purpose utilities for IBIS-AMI models.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   April 14, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

import numpy as np

from ..common     import Rvec
from ..ami.parser import ami_parse


def get_cdr_adaptation(ami_out_params: list[str]) -> Rvec:
    """
    Extract the CDR adaptation from the given list of AMI output parameter strings.

    Args:
        ami_out_params: List of AMI output parameter strings.

    Returns:
        CDR adaptation if found; empty vector otherwise.
    """

    cdr_ui_estimates: list[float] = []
    cdr_ui_found: bool = False
    _, param_pairs = ami_parse(ami_out_params[0])
    for key, value_strs in param_pairs:  # type: ignore
        key_lower_case = key.lower()
        if "cdr" in key_lower_case and (
            "ui" in key_lower_case or "per" in key_lower_case):
            cdr_ui_estimates.append(float(value_strs[0]))
            cdr_ui_found = True
            break
    if cdr_ui_found:
        for _, param_pairs in map(ami_parse, ami_out_params[1:]):
            for key, value_strs in param_pairs:  # type: ignore
                key_lower_case = key.lower()
                if "cdr" in key_lower_case and (
                    "ui" in key_lower_case or "per" in key_lower_case):
                    cdr_ui_estimates.append(float(value_strs[0]))
                    break
    return np.array(cdr_ui_estimates)


def get_dfe_adaptation(ami_out_params: list[str]) -> dict[str, Rvec]:
    """
    Extract the individual DFE tap weight adaptation curves
    from the given list of AMI output parameter strings.

    Args:
        ami_out_params: List of AMI output parameter strings.

    Returns:
        Dictionary of DFE tap weight adaptation vectors.
        (Dictionary keys are the dicovered parameter names.)
    """

    dfe_tap_weights: dict[str, Rvec] = {}
    _, param_pairs = ami_parse(ami_out_params[0])
    for key, value_strs in param_pairs:  # type: ignore
        key_lower_case = key.lower()
        if "dfe" in key_lower_case and "tap" in key_lower_case:
            dfe_tap_weights[key] = np.array([float(value_strs[0])])
    for _, param_pairs in map(ami_parse, ami_out_params[1:]):
        for key, value_strs in param_pairs:  # type: ignore
            if key in dfe_tap_weights:
                dfe_tap_weights[key] = np.append(dfe_tap_weights[key],
                                                 float(value_strs[0]))
    return dfe_tap_weights
