"Generic AMI model testing sweep definition file."

# You may place as many `TestSweep` subclass definitions as you wish in this file.
# 
# You may have as many files like this one as you wish in your test sweep definition directory
# (i.e. - the directory you give the `test_models` command, via its `-p` parameter).

# Only those Python files found in the top level of your test sweep definition directory
# will be searched for `TestSweep` subclasses. This allows you to deactivate certain
# test sweep definition files, by placing them in, for instance, a "deactivated"
# subfolder.

from typing                         import Any
import numpy as np
from pyibisami.testing.test_defs    import (
    TestDefinition, TestSweep, perfect_channel, lossy_channel, reflective_channel)

# Test invariants - You may change these.
BIT_RATE = 10e9
OSF      = 32
CHANNEL_RESPONSE_BITS = 20
LOSSY_CHANNEL_BW      = 0.1    # Normalized to `BIT_RATE`.

# Global definitions - DO NOT CHANGE THESE!
bit_time        = 1 / BIT_RATE
sample_interval = bit_time / OSF

# This will be picked up by the `test-model` command, because it is a subclass of `TestSweep`.
class MyTestSweep(TestSweep):
    "Generic example of `TestSweep` subclass definition."

    # Change and/or copy/paste, as required to complete your own testing goals.

    # Initial parameter definitions.
    ami_params: dict[str, Any] = @(f"{ami_params.__repr__()}")

    sim_params: dict[str, Any] = {
        'channel_response': perfect_channel(
            OSF, CHANNEL_RESPONSE_BITS, sample_interval),
        'sample_interval': sample_interval,
        'bit_time': bit_time,
        'nbits': 1_000
    }

    def test_sweep(self):
        "Generates individual test cases."

        # Perfect channel.
        yield TestDefinition(
            "Perfect Channel @ 10 Gbps NRZ w/ 32x OSF (CTLE = 0)",
            self.ami_params, self.sim_params)

        # Lossy channel.
        self.ami_params.update({
            # Place necessary parameter overrides here.
            # Potential examples:
            # 'ctle_mag': 9.0,
            # 'dfe_vout': 0.25,
            # 'dfe_gain': 0.2,
            })
        self.sim_params.update({
            'channel_response': lossy_channel(
                OSF, CHANNEL_RESPONSE_BITS, sample_interval, bw=LOSSY_CHANNEL_BW),
            })
        yield TestDefinition(
            "Lossy Channel @ 10 Gbps NRZ w/ 32x OSF (CTLE = 9dB)",
            self.ami_params, self.sim_params)

        # Reflective channel.
        self.ami_params.update({
            # Place necessary parameter overrides here.
            # Potential examples:
            # 'ctle_mag': 3.0,
            # 'dfe_vout': 0.4,
            # 'dfe_gain': 0.1,
            })
        self.sim_params.update({
            'channel_response': reflective_channel(
                OSF, CHANNEL_RESPONSE_BITS, sample_interval),
            })
        yield TestDefinition(
            "Reflective Channel @ 10 Gbps NRZ w/ 32x OSF (CTLE = 3dB)",
            self.ami_params, self.sim_params)
