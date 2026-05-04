"Different channel types w/ fixed CTLE and adaptive DFE."

from typing                         import Any
import numpy as np
from pyibisami.testing.test_defs    import (
    TestDefinition, TestSweep, perfect_channel, lossy_channel, reflective_channel)

# Test invariants.
BIT_RATE = 10e9
OSF      = 32
CHANNEL_RESPONSE_BITS = 20
LOSSY_CHANNEL_BW      = 0.05    # Normalized to `BIT_RATE`.

# Global definitions
bit_time        = 1 / BIT_RATE
sample_interval = bit_time / OSF

class MyTestSweep(TestSweep):
    "CTLE gain and DFE Vout matched to channel type."

    # Initial parameter definitions.
    ami_params: dict[str, Any] = {
        'root_name' : 'example_rx',
        'ctle_mode': 1,
        'ctle_mag': 0.0,
        'ctle_bandwidth': 1.2 * BIT_RATE,
        'ctle_freq': BIT_RATE / 2,
        'ctle_dcgain': 0.0,
        'dfe_mode':  2,
        'dfe_ntaps': 5,
        'dfe_vout':  0.5,
        'dfe_gain':  0.02,
        'dfe_tap1': 0.0,
        'dfe_tap2': 0.0,
        'dfe_tap3': 0.0,
        'dfe_tap4': 0.0,
        'dfe_tap5': 0.0,
        'debug': {'dump_adaptation_input': False, 'dump_dfe_adaptation': False, 'dbg_enable': False},
    }

    sim_params: dict[str, Any] = {
        'channel_response': perfect_channel(
            OSF, CHANNEL_RESPONSE_BITS, sample_interval),
        'sample_interval': sample_interval,
        'bit_time': bit_time,
        'nbits': 1_000
    }

    def test_sweep(self):
        # Perfect channel.
        yield TestDefinition(
            "Perfect Channel @ 10 Gbps NRZ w/ 32x OSF (CTLE = 0)",
            self.ami_params, self.sim_params)

        # Lossy channel.
        self.ami_params.update({
            'ctle_mag': 9.0,
            'dfe_vout': 0.25,
            })
        self.sim_params.update({
            'channel_response': lossy_channel(
                OSF, CHANNEL_RESPONSE_BITS, sample_interval),
            })
        yield TestDefinition(
            "Lossy Channel @ 10 Gbps NRZ w/ 32x OSF (CTLE = 9dB)",
            self.ami_params, self.sim_params)

        # Reflective channel.
        self.ami_params.update({
            'ctle_mag': 3.0,
            'dfe_vout': 0.4,
            })
        self.sim_params.update({
            'channel_response': reflective_channel(
                OSF, CHANNEL_RESPONSE_BITS, sample_interval),
            })
        yield TestDefinition(
            "Reflective Channel @ 10 Gbps NRZ w/ 32x OSF (CTLE = 3dB)",
            self.ami_params, self.sim_params)
