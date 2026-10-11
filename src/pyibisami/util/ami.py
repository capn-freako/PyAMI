"""
General purpose utilities for IBIS-AMI models.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   April 14, 2026

Copyright (c) 2026 David Banas; All rights reserved World wide.
"""

import logging
from typing import Any, Optional

import numpy as np
from parsec import ParseError

from ..common     import Rvec
from ..ami.parser import ami_parse

logger = logging.getLogger(__name__)


def _parse_out_params(ami_out_params: list[str], purpose: str) -> Optional[list[Any]]:
    """
    Parse each AMI output parameter string into its list of (name, values) pairs.

    Args:
        ami_out_params: List of AMI output parameter strings.
        purpose: What the parsed parameters are needed for (used in the warning).

    Returns:
        One list of (name, values) pairs per string;
        ``None`` (with a logged warning) if any string can't be parsed.
    """

    parsed = []
    for params in ami_out_params:
        try:
            parsed.append(ami_parse(params)[1])
        except ParseError as err:
            logger.warning(
                "Skipping %s: can't parse the model's AMI output parameters (%s): %.80s...", purpose, err, params)
            return None
    return parsed


def get_cdr_adaptation(ami_out_params: list[str]) -> Rvec:
    """
    Extract the CDR adaptation from the given list of AMI output parameter strings.

    Args:
        ami_out_params: List of AMI output parameter strings.

    Returns:
        CDR adaptation if found; empty vector otherwise
        (including when the parameter strings can't be parsed).
    """

    cdr_ui_estimates: list[float] = []
    parsed = _parse_out_params(ami_out_params, "CDR adaptation")
    if not parsed:
        return np.array(cdr_ui_estimates)
    cdr_ui_found: bool = False
    for key, value_strs in parsed[0]:
        key_lower_case = key.lower()
        if "cdr" in key_lower_case and (
           "ui" in key_lower_case or "per" in key_lower_case):
            cdr_ui_estimates.append(float(value_strs[0]))
            cdr_ui_found = True
            break
    if cdr_ui_found:
        for param_pairs in parsed[1:]:
            for key, value_strs in param_pairs:
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
        Empty if the parameter strings can't be parsed.
    """

    dfe_tap_weights: dict[str, Rvec] = {}
    parsed = _parse_out_params(ami_out_params, "DFE adaptation")
    if not parsed:
        return dfe_tap_weights
    for key, value_strs in parsed[0]:
        key_lower_case = key.lower()
        if "dfe" in key_lower_case and "tap" in key_lower_case:
            dfe_tap_weights[key] = np.array([float(value_strs[0])])
    for param_pairs in parsed[1:]:
        for key, value_strs in param_pairs:
            if key in dfe_tap_weights:
                dfe_tap_weights[key] = np.append(dfe_tap_weights[key],
                                                 float(value_strs[0]))
    return dfe_tap_weights
