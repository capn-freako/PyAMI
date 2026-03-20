"""
Useful functions for testing IBIS-AMI models.

Original author: David Banas <capn.freako@gmail.com>
Original date: March 19, 2026

Copyright (c) 2026 David Banas; all rights reserved World wide.
"""

from typing import Any

import numpy as np
from scipy.interpolate import interp1d

from ..common import Rvec
from ..ami.model import AMIModel, AMIModelInitializer


def do_samples_per_bit(
    model: AMIModel, initializer: AMIModelInitializer, channel_response: Rvec,
    sample_interval: float, bit_rate: float, nbits: int
) -> list[tuple[dict[str, Any], int]]:
    """
    Run the "Samples per Bit" comparison.

    Args:
        model: The AMI model to test.
        initializer: The AMI model initializer to use/customize.
        channel_response: The analog channel impulse response.
        sample_interval: The time spacing between successive elements of ``channel_response``.
        bit_rate: The assumed symbol rate.
        nbits: The number of bits to use for model characterization.

    Returns:
        A list of model response dictionaries, one for each oversampling rate tried.
    """

    # Do not interpolate deltas.
    len_ch_resp = len(channel_response)
    t = np.arange(0, len_ch_resp) * sample_interval
    nspui = int(1 / (sample_interval * bit_rate))

    def interp(x, ts):
        if not any(channel_response[1:]):  # delta?
            len_x = len(x)
            if len_x > len_ch_resp:
                rslt = np.pad(channel_response, (0, len_x - len_ch_resp),
                           mode="constant", constant_values=0)
            else:
                rslt = channel_response[:len_x]
            return rslt * sample_interval / ts
        else:
            krnl = interp1d(
                t, channel_response, kind="cubic",
                bounds_error=False, fill_value="extrapolate", assume_sorted=True
            )  # interpolation "kernel"
            return krnl(x)

    model_responses = []
    for osf in [nspui//2, nspui, nspui*2]:
        ts = 1 / (bit_rate * osf)
        _row_size = nbits * osf
        _t = np.array([n * ts for n in range(_row_size)])
        
        initializer.sample_interval = ts
        initializer.channel_response = interp(_t, ts)
        model.initialize(initializer)
        model_responses.append((model.get_responses(), osf))

    return model_responses
